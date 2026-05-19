from decimal import Decimal, InvalidOperation

from django.http import FileResponse, Http404
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from .models import Service, ServiceOptionGroup, ServiceOption
from .models import (
    ServiceOrder,
    ServiceOrderAttachment,
    ServiceOrderComment,
    ServiceOrderItem,
    ServiceOrderItemOption,
)
from .models import AuditLog
from .emails import (
    build_order_cancellation_email,
    build_order_confirmation_email,
    build_status_change_email,
    send_customer_email,
)
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.http import url_has_allowed_host_and_scheme
from .choices import (
    ServiceOrderStatus,
    can_change_order_status,
    get_available_order_status_choices,
)
from .validators import (
    get_attachment_error,
    get_customer_order_errors,
    get_device_order_errors,
    normalize_phone_number,
)



STATUS_LABELS = dict(ServiceOrderStatus.choices)


def redirect_staff_from_client_area(request):
    if request.user.is_staff:
        return redirect("tech_dashboard")
    return None


def home(request):
    staff_redirect = redirect_staff_from_client_area(request)
    if staff_redirect:
        return staff_redirect

    return render(request, "orders/home.html")


def get_staff_redirect_url(request, next_url=None):
    target = next_url or request.GET.get("next") or request.POST.get("next") or ""

    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target

    return "/tech/dashboard/"


def staff_login(request):
    next_url = request.GET.get("next") or request.POST.get("next") or ""
    error = None

    if request.user.is_staff:
        return redirect(get_staff_redirect_url(request, next_url))

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        user = authenticate(request, username=username, password=password)

        if user is None:
            error = "Nieprawidłowy login lub hasło."
        elif not user.is_staff:
            error = "To konto nie ma dostępu do panelu pracownika."
        else:
            auth_login(request, user)
            return redirect(get_staff_redirect_url(request, next_url))

    return render(
        request,
        "orders/staff_login.html",
        {
            "error": error,
            "next_url": next_url,
        },
    )


def staff_logout(request):
    if request.method == "POST":
        auth_logout(request)

    return redirect("home")


def get_verified_order(order_number: str, email: str, phone: str):
    order = ServiceOrder.objects.filter(order_number=order_number).first()

    if not order:
        return None

    email_ok = email and (order.customer_email.lower() == email)
    phone_ok = phone and (
        normalize_phone_number(order.customer_phone) == normalize_phone_number(phone)
    )

    if not (email_ok or phone_ok):
        return None

    return order


def remember_verified_order(request, order):
    verified_order_ids = request.session.get("verified_order_ids", [])
    if order.id not in verified_order_ids:
        verified_order_ids.append(order.id)
        request.session["verified_order_ids"] = verified_order_ids


def can_access_attachment(request, attachment):
    if request.user.is_staff:
        return True

    if attachment.visibility != ServiceOrderAttachment.Visibility.PUBLIC:
        return False

    return attachment.order_id in request.session.get("verified_order_ids", [])


def attachment_download(request, attachment_id: int):
    attachment = get_object_or_404(ServiceOrderAttachment, pk=attachment_id)

    if not can_access_attachment(request, attachment):
        raise Http404

    return FileResponse(
        attachment.file.open("rb"),
        as_attachment=False,
        filename=attachment.original_name,
    )


def track_order(request):
    """
    Guest access: śledzenie zlecenia bez logowania.

    GET  -> pokazuje formularz
    POST -> weryfikuje dane i pokazuje wynik
    """
    staff_redirect = redirect_staff_from_client_area(request)
    if staff_redirect:
        return staff_redirect

    context = {
        "result": None,
        "error": None,
        "message": None,
        "order_number_default": (request.GET.get("order_number") or "").strip().upper(),
    }

    if request.method == "POST":
        action = request.POST.get("action") or "track_order"
        order_number = (request.POST.get("order_number") or "").strip().upper()
        email = (request.POST.get("email") or "").strip().lower()
        phone = (request.POST.get("phone") or "").strip()

        # Minimalne wymaganie: numer zlecenia + (email albo phone)
        if not order_number or (not email and not phone):
            context["error"] = "Podaj numer zlecenia oraz e-mail lub numer telefonu."
            return render(request, "orders/track_order.html", context)

        order = get_verified_order(order_number, email, phone)

        if not order:
            context["error"] = "Nie znaleziono zlecenia dla podanych danych."
            return render(request, "orders/track_order.html", context)

        remember_verified_order(request, order)

        if action == "cancel_order":
            if order.can_cancel():
                old_status = order.status
                order.status = ServiceOrderStatus.CANCELED
                order.save()

                AuditLog.objects.create(
                    order=order,
                    entity_type=AuditLog.EntityType.SERVICE_ORDER,
                    entity_id=order.id,
                    action=AuditLog.Action.ORDER_CANCELED,
                    old_value=old_status,
                    new_value=order.status,
                    performed_by=None,
                )

                subject, message = build_order_cancellation_email(order)
                email_sent = send_customer_email(subject, message, order.customer_email)

                if email_sent:
                    context["message"] = "Zlecenie zostało anulowane."
                else:
                    context["message"] = (
                        "Zlecenie zostało anulowane. Nie udało się wysłać wiadomości e-mail do klienta."
                    )
            else:
                context["error"] = (
                    "Anulowanie online jest dostępne tylko dla nowych zleceń. "
                    "Skontaktuj się telefonicznie z serwisem."
                )

        elif action == "accept_repair":
            if order.can_accept_repair():
                order.customer_accepted_repair = True
                order.save()

                AuditLog.objects.create(
                    order=order,
                    entity_type=AuditLog.EntityType.SERVICE_ORDER,
                    entity_id=order.id,
                    action=AuditLog.Action.REPAIR_ACCEPTED,
                    old_value="False",
                    new_value="True",
                    performed_by=None,
                )

                context["message"] = "Naprawa została zaakceptowana."
            elif order.customer_accepted_repair:
                context["message"] = "Naprawa została już zaakceptowana."
            else:
                context["error"] = "Akceptacja naprawy nie jest jeszcze dostępna."

        public_comments = ServiceOrderComment.objects.filter(
            order=order,
            visibility=ServiceOrderComment.Visibility.PUBLIC,
        ).order_by("created_at")

        public_attachments = ServiceOrderAttachment.objects.filter(
            order=order,
            visibility=ServiceOrderAttachment.Visibility.PUBLIC,
        ).order_by("created_at")

        audit_entries = AuditLog.objects.filter(
            order=order,
            action__in=[
                AuditLog.Action.ORDER_CREATED,
                AuditLog.Action.STATUS_CHANGED,
                AuditLog.Action.ESTIMATE_SET,
                AuditLog.Action.ORDER_CANCELED,
                AuditLog.Action.DIAGNOSIS_UPDATED,
                AuditLog.Action.REPAIR_ACCEPTED,
                AuditLog.Action.TECHNICIAN_ASSIGNED,
                AuditLog.Action.ATTACHMENT_ADDED,
            ],
        ).order_by("performed_at")

        audit_timeline = []
        for a in audit_entries:
            if a.action == AuditLog.Action.ORDER_CREATED:
                audit_timeline.append((a.performed_at, "Zlecenie przyjęte"))
            elif a.action == AuditLog.Action.STATUS_CHANGED:
                old_label = STATUS_LABELS.get(a.old_value, a.old_value)
                new_label = STATUS_LABELS.get(a.new_value, a.new_value)
                audit_timeline.append((a.performed_at, f"Zmiana statusu: {old_label} → {new_label}"))
            elif a.action == AuditLog.Action.ESTIMATE_SET:
                old_txt = "brak" if not a.old_value or a.old_value == "None" else a.old_value
                new_txt = "brak" if not a.new_value or a.new_value == "None" else a.new_value
                audit_timeline.append(
                    (a.performed_at, f"Zmiana estymacji: {old_txt} → {new_txt}")
                )
            elif a.action == AuditLog.Action.ORDER_CANCELED:
                audit_timeline.append((a.performed_at, "Zlecenie anulowane"))
            elif a.action == AuditLog.Action.DIAGNOSIS_UPDATED:
                audit_timeline.append((a.performed_at, "Aktualizacja diagnozy i rozliczenia"))
            elif a.action == AuditLog.Action.REPAIR_ACCEPTED:
                audit_timeline.append((a.performed_at, "Klient zaakceptował naprawę"))
            elif a.action == AuditLog.Action.TECHNICIAN_ASSIGNED:
                audit_timeline.append((a.performed_at, f"Przypisano technika: {a.new_value}"))
            elif a.action == AuditLog.Action.ATTACHMENT_ADDED:
                audit_timeline.append((a.performed_at, "Dodano załącznik"))





        context["result"] = {
            "order_number": order.order_number,
            "status": order.get_status_display(),
            "estimated_completion_at": order.estimated_completion_at,
            "device_type": order.get_device_type_display() if order.device_type else "",
            "device_brand": order.device_brand,
            "device_model": order.device_model,
            "device_issue_description": order.device_issue_description,
            "diagnosis": order.diagnosis,
            "repair_notes": order.repair_notes,
            "final_price": order.final_price,
            "customer_accepted_repair": order.customer_accepted_repair,
            "can_accept_repair": order.can_accept_repair(),
            "has_service_result": bool(
                order.diagnosis
                or order.repair_notes
                or order.final_price is not None
                or order.customer_accepted_repair
            ),
            "comments": public_comments,
            "attachments": public_attachments,
            "audit_timeline": audit_timeline,
            "can_cancel": order.can_cancel(),
            "email": email,
            "phone": phone,
        }



    return render(request, "orders/track_order.html", context)


def service_catalog(request):
    """
    Katalog usług dla klienta (read-only).
    Pokazuje tylko aktywne usługi.
    """
    staff_redirect = redirect_staff_from_client_area(request)
    if staff_redirect:
        return staff_redirect

    services = Service.objects.filter(is_active=True).order_by("name")

    return render(
        request,
        "orders/service_catalog.html",
        {"services": services},
    )


def service_configurator(request, service_id: int):
    """
    Konfigurator usługi dla klienta:
    - pokazuje grupy opcji i dostępne opcje
    - po POST liczy widełki ceny (min/max)
    """
    staff_redirect = redirect_staff_from_client_area(request)
    if staff_redirect:
        return staff_redirect

    service = get_object_or_404(Service, pk=service_id, is_active=True)

    groups = ServiceOptionGroup.objects.filter(
        service=service,
        is_active=True,
    ).order_by("sort_order", "id")

    # Przygotujemy strukturę: grupa -> opcje
    group_options = []
    for g in groups:
        options = ServiceOption.objects.filter(
            group=g,
            is_active=True,
        ).order_by("sort_order", "id")
        group_options.append((g, options))

    result = None
    selected_option_ids = set()

    customer_defaults = {
        "customer_name": "",
        "customer_email": "",
        "customer_phone": "",
        "customer_consent": False,
        "device_type": "",
        "device_brand": "",
        "device_model": "",
        "device_issue_description": "",
    }

    if request.method == "POST":

        customer_defaults = {
            "customer_name": request.POST.get("customer_name", ""),
            "customer_email": request.POST.get("customer_email", ""),
            "customer_phone": request.POST.get("customer_phone", ""),
            "customer_consent": request.POST.get("customer_consent") == "on",
            "device_type": request.POST.get("device_type", ""),
            "device_brand": request.POST.get("device_brand", ""),
            "device_model": request.POST.get("device_model", ""),
            "device_issue_description": request.POST.get("device_issue_description", ""),
        }

        # Zbieramy zaznaczone opcje z formularza
        posted_option_ids = []

        for g, _opts in group_options:
            field_name = f"group_{g.id}"

            if g.selection_type == ServiceOptionGroup.SelectionType.SINGLE:
                chosen = request.POST.get(field_name)
                if chosen:
                    try:
                        posted_option_ids.append(int(chosen))
                    except ValueError:
                        pass
            else:
                chosen_list = request.POST.getlist(field_name)
                for chosen in chosen_list:
                    if chosen:
                        try:
                            posted_option_ids.append(int(chosen))
                        except ValueError:
                            pass

        selected_options = list(
            ServiceOption.objects.filter(
                id__in=posted_option_ids,
                group__service=service,
                group__is_active=True,
                is_active=True,
            )
        )
        selected_option_ids = {option.id for option in selected_options}
        selected_group_ids = {option.group_id for option in selected_options}
        required_option_errors = [
            f'Wybierz opcję w grupie "{group.name}".'
            for group, _options in group_options
            if group.is_required and group.id not in selected_group_ids
        ]

        total_min = service.base_price_min
        total_max = service.base_price_max
        total_duration_minutes = service.base_duration_minutes

        for opt in selected_options:
            total_min += opt.price_delta_min
            total_max += opt.price_delta_max
            total_duration_minutes += opt.duration_delta_minutes

        result = {
            "has_price": not required_option_errors,
            "total_min": total_min,
            "total_max": total_max,
            "total_duration_minutes": max(total_duration_minutes, 0),
            "selected_options": selected_options,
        }
        if required_option_errors:
            result["error"] = " ".join(required_option_errors)

        action = request.POST.get("action")

        if action == "create_order":
            customer_name = (request.POST.get("customer_name") or "").strip()
            customer_email = (request.POST.get("customer_email") or "").strip().lower()
            customer_phone = (request.POST.get("customer_phone") or "").strip()
            customer_consent = request.POST.get("customer_consent") == "on"
            device_type = (request.POST.get("device_type") or "").strip()
            device_brand = (request.POST.get("device_brand") or "").strip()
            device_model = (request.POST.get("device_model") or "").strip()
            device_issue_description = (request.POST.get("device_issue_description") or "").strip()
            uploaded_file = request.FILES.get("attachment")
            customer_errors = get_customer_order_errors(
                customer_name,
                customer_email,
                customer_phone,
                customer_consent,
            )
            device_errors = get_device_order_errors(
                device_type,
                device_brand,
                device_issue_description,
            )
            attachment_error = get_attachment_error(uploaded_file) if uploaded_file else None

            if required_option_errors or customer_errors or device_errors or attachment_error:
                result["error"] = " ".join(
                    [
                        *required_option_errors,
                        *customer_errors,
                        *device_errors,
                        *([attachment_error] if attachment_error else []),
                    ]
                )
            else:
                order = ServiceOrder.objects.create(
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                    device_type=device_type,
                    device_brand=device_brand,
                    device_model=device_model,
                    device_issue_description=device_issue_description,
                )

                AuditLog.objects.create(
                    order=order,
                    entity_type=AuditLog.EntityType.SERVICE_ORDER,
                    entity_id=order.id,
                    action=AuditLog.Action.ORDER_CREATED,
                    new_value=f"status={order.status}",
                    performed_by=None,
                )

                if uploaded_file:
                    attachment = ServiceOrderAttachment.objects.create(
                        order=order,
                        visibility=ServiceOrderAttachment.Visibility.PUBLIC,
                        file=uploaded_file,
                        original_name=uploaded_file.name,
                        uploaded_by=None,
                    )

                    AuditLog.objects.create(
                        order=order,
                        entity_type=AuditLog.EntityType.SERVICE_ORDER,
                        entity_id=order.id,
                        action=AuditLog.Action.ATTACHMENT_ADDED,
                        new_value=f"visibility={attachment.visibility}; file={attachment.original_name}",
                        performed_by=None,
                    )

                order_item = ServiceOrderItem.objects.create(
                    order=order,
                    service=service,
                    service_name_snapshot=service.name,
                    base_price_min_snapshot=service.base_price_min,
                    base_price_max_snapshot=service.base_price_max,
                    calculated_price_min=total_min,
                    calculated_price_max=total_max,
                )

                for opt in selected_options:
                    ServiceOrderItemOption.objects.create(
                        order_item=order_item,
                        option=opt,
                        option_name_snapshot=opt.name,
                        price_delta_min_snapshot=opt.price_delta_min,
                        price_delta_max_snapshot=opt.price_delta_max,
                    )

                subject, message = build_order_confirmation_email(order)
                email_sent = send_customer_email(subject, message, order.customer_email)
                request.session[f"order_created_email_status_{order.order_number}"] = (
                    "sent" if email_sent else "failed"
                )

                return redirect("order_created", order_number=order.order_number)
            customer_defaults = {
                "customer_name": request.POST.get("customer_name", "") if request.method == "POST" else "",
                "customer_email": request.POST.get("customer_email", "") if request.method == "POST" else "",
                "customer_phone": request.POST.get("customer_phone", "") if request.method == "POST" else "",
                "customer_consent": request.POST.get("customer_consent") == "on",
                "device_type": request.POST.get("device_type", ""),
                "device_brand": request.POST.get("device_brand", ""),
                "device_model": request.POST.get("device_model", ""),
                "device_issue_description": request.POST.get("device_issue_description", ""),
            }

    return render(
        request,
        "orders/service_configurator.html",
        {
            "service": service,
            "group_options": group_options,
            "result": result,
            "customer_defaults": customer_defaults,
            "selected_option_ids": selected_option_ids,
        },
    )


def order_created(request, order_number: str):
    """
    Strona potwierdzenia utworzenia zlecenia (GET).
    """
    staff_redirect = redirect_staff_from_client_area(request)
    if staff_redirect:
        return staff_redirect

    email_status = request.session.pop(f"order_created_email_status_{order_number}", "unknown")
    return render(
        request,
        "orders/order_created.html",
        {
            "order_number": order_number,
            "track_url": f"/track/?order_number={order_number}",
            "email_status": email_status,
        },
    )

@staff_member_required(login_url="staff_login")
def tech_dashboard(request):
    """
    Dashboard technika: podział zleceń na Nowe / W toku / Przeterminowane.
    """
    selected_status = request.GET.get("status") or ""
    if selected_status not in dict(ServiceOrderStatus.choices):
        selected_status = ""

    selected_device_type = request.GET.get("device_type") or ""
    if selected_device_type not in dict(ServiceOrder.DeviceType.choices):
        selected_device_type = ""

    scope = request.GET.get("scope") or "mine"
    if scope not in {"mine", "all", "unassigned"}:
        scope = "mine"

    search_query = (request.GET.get("q") or "").strip()

    if scope == "mine":
        scoped_orders = ServiceOrder.objects.filter(assigned_technician=request.user)
    elif scope == "unassigned":
        scoped_orders = ServiceOrder.objects.filter(assigned_technician__isnull=True)
    else:
        scoped_orders = ServiceOrder.objects.all()

    orders_new = scoped_orders.filter(status=ServiceOrderStatus.NEW).order_by("-created_at")

    orders_in_progress = scoped_orders.filter(
        status__in=[
            ServiceOrderStatus.RECEIVED,
            ServiceOrderStatus.IN_PROGRESS,
            ServiceOrderStatus.WAITING_FOR_PARTS,
        ]
    ).order_by("-created_at")

    orders_ready = scoped_orders.filter(status=ServiceOrderStatus.READY).order_by("-created_at")

    selected_status_label = None
    if selected_status:
        selected_status_label = STATUS_LABELS[selected_status]

    selected_device_type_label = None
    if selected_device_type:
        selected_device_type_label = dict(ServiceOrder.DeviceType.choices)[selected_device_type]

    dashboard_counts = {
        "new": orders_new.count(),
        "in_progress": orders_in_progress.count(),
        "ready": orders_ready.count(),
        "active": scoped_orders.exclude(
            status__in=[ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELED]
        ).count(),
        "completed": scoped_orders.filter(status=ServiceOrderStatus.COMPLETED).count(),
    }

    all_active = scoped_orders.exclude(
        status__in=[ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELED]
    ).order_by("-created_at")
    orders_overdue = [o for o in all_active if o.is_overdue()]
    dashboard_counts["overdue"] = len(orders_overdue)

    if selected_status:
        dashboard_queryset = scoped_orders.filter(status=selected_status)
    else:
        dashboard_queryset = scoped_orders.exclude(
            status__in=[ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELED]
        )

    if selected_device_type:
        dashboard_queryset = dashboard_queryset.filter(device_type=selected_device_type)

    if search_query:
        dashboard_queryset = dashboard_queryset.filter(
            Q(order_number__icontains=search_query)
            | Q(customer_name__icontains=search_query)
            | Q(customer_email__icontains=search_query)
            | Q(customer_phone__icontains=search_query)
            | Q(device_brand__icontains=search_query)
            | Q(device_model__icontains=search_query)
            | Q(device_issue_description__icontains=search_query)
            | Q(diagnosis__icontains=search_query)
            | Q(repair_notes__icontains=search_query)
        )

    if selected_status:
        dashboard_orders = list(dashboard_queryset.order_by("-created_at"))
    else:
        status_priority = {
            ServiceOrderStatus.NEW: 1,
            ServiceOrderStatus.IN_PROGRESS: 2,
            ServiceOrderStatus.WAITING_FOR_PARTS: 3,
            ServiceOrderStatus.RECEIVED: 4,
            ServiceOrderStatus.READY: 5,
        }
        dashboard_orders = sorted(
            dashboard_queryset.order_by("-created_at"),
            key=lambda order: (
                0 if order.is_overdue() else 1,
                status_priority.get(order.status, 99),
                order.created_at,
            ),
        )

    return render(
        request,
        "orders/tech_dashboard.html",
        {
            "dashboard_orders": dashboard_orders,
            "dashboard_counts": dashboard_counts,
            "device_type_choices": ServiceOrder.DeviceType.choices,
            "scope": scope,
            "scope_label": {
                "mine": "Moje zlecenia",
                "all": "Wszystkie zlecenia",
                "unassigned": "Nieprzypisane",
            }[scope],
            "has_dashboard_filters": bool(
                selected_status or selected_device_type or search_query
            ),
            "search_query": search_query,
            "selected_device_type": selected_device_type,
            "selected_device_type_label": selected_device_type_label,
            "selected_status": selected_status,
            "selected_status_label": selected_status_label,
            "status_choices": ServiceOrderStatus.choices,
        },
    )


@staff_member_required(login_url="staff_login")
def tech_order_detail(request, order_number: str):
    """
    Widok szczegółów zlecenia dla technika.
    """
    order = get_object_or_404(ServiceOrder, order_number=order_number)
    message = None
    error = None

    if request.method == "POST":
        action = request.POST.get("action") or "update_order"

        if action == "claim_order":
            if order.assigned_technician is None:
                claimed = ServiceOrder.objects.filter(
                    pk=order.pk,
                    assigned_technician__isnull=True,
                ).update(
                    assigned_technician=request.user,
                    updated_at=timezone.now(),
                )
                order.refresh_from_db()

                if claimed:
                    AuditLog.objects.create(
                        order=order,
                        entity_type=AuditLog.EntityType.SERVICE_ORDER,
                        entity_id=order.id,
                        action=AuditLog.Action.TECHNICIAN_ASSIGNED,
                        old_value="",
                        new_value=request.user.username,
                        performed_by=request.user,
                    )

                    message = "Zlecenie zostało przypisane do Ciebie."
                elif order.assigned_technician == request.user:
                    message = "To zlecenie jest już przypisane do Ciebie."
                else:
                    error = "Zlecenie jest już przypisane do innego technika."
            elif order.assigned_technician == request.user:
                message = "To zlecenie jest już przypisane do Ciebie."
            else:
                error = "Zlecenie jest już przypisane do innego technika."

        elif action == "update_order":
            new_status = request.POST.get("status")
            estimate_raw = (request.POST.get("estimated_completion_at") or "").strip()
            notify_customer = request.POST.get("notify_customer") == "on"

            old_status = order.status
            old_estimate = order.estimated_completion_at
            email_sent = None

            if new_status not in dict(ServiceOrderStatus.choices):
                error = "Wybrano nieprawidłowy status."
            elif not can_change_order_status(order.status, new_status):
                error = "Taka zmiana statusu nie jest dozwolona w aktualnym etapie obsługi."
            else:
                new_estimate = None
                if estimate_raw:
                    parsed = parse_datetime(estimate_raw.replace(" ", "T"))
                    if parsed is None:
                        error = "Nieprawidłowy format estymacji. Użyj YYYY-MM-DD HH:MM."
                    else:
                        new_estimate = parsed
                        if timezone.is_naive(new_estimate):
                            new_estimate = timezone.make_aware(new_estimate)

                if error is None:
                    order.status = new_status
                    order.estimated_completion_at = new_estimate
                    order.save()

                    if old_status != order.status:
                        AuditLog.objects.create(
                            order=order,
                            entity_type=AuditLog.EntityType.SERVICE_ORDER,
                            entity_id=order.id,
                            action=AuditLog.Action.STATUS_CHANGED,
                            old_value=old_status,
                            new_value=order.status,
                            performed_by=request.user,
                        )

                        if notify_customer:
                            subject, message = build_status_change_email(order)
                            email_sent = send_customer_email(subject, message, order.customer_email)

                    if old_estimate != order.estimated_completion_at:
                        AuditLog.objects.create(
                            order=order,
                            entity_type=AuditLog.EntityType.SERVICE_ORDER,
                            entity_id=order.id,
                            action=AuditLog.Action.ESTIMATE_SET,
                            old_value=str(old_estimate),
                            new_value=str(order.estimated_completion_at),
                            performed_by=request.user,
                        )

                    if notify_customer and old_status != order.status and email_sent:
                        message = "Zlecenie zostało zaktualizowane, a klient otrzymał wiadomość e-mail."
                    elif notify_customer and old_status != order.status and email_sent is False:
                        message = (
                            "Zlecenie zostało zaktualizowane. Nie udało się wysłać wiadomości e-mail do klienta."
                        )
                    else:
                        message = "Zlecenie zostało zaktualizowane."

        elif action == "add_comment":
            visibility = request.POST.get("visibility")
            content = (request.POST.get("content") or "").strip()

            if visibility not in dict(ServiceOrderComment.Visibility.choices):
                error = "Wybrano nieprawidłowy typ komentarza."
            elif not content:
                error = "Treść komentarza nie może być pusta."
            else:
                comment = ServiceOrderComment.objects.create(
                    order=order,
                    visibility=visibility,
                    content=content,
                )

                AuditLog.objects.create(
                    order=order,
                    entity_type=AuditLog.EntityType.SERVICE_ORDER_COMMENT,
                    entity_id=comment.id,
                    action=AuditLog.Action.COMMENT_ADDED,
                    new_value=f"visibility={comment.visibility}",
                    performed_by=request.user,
                )

                message = "Komentarz został dodany."

        elif action == "add_attachment":
            visibility = request.POST.get("visibility")
            uploaded_file = request.FILES.get("file")
            attachment_error = get_attachment_error(uploaded_file)

            if visibility not in dict(ServiceOrderAttachment.Visibility.choices):
                error = "Wybrano nieprawidłowy typ załącznika."
            elif attachment_error:
                error = attachment_error
            else:
                attachment = ServiceOrderAttachment.objects.create(
                    order=order,
                    visibility=visibility,
                    file=uploaded_file,
                    original_name=uploaded_file.name,
                    uploaded_by=request.user,
                )

                AuditLog.objects.create(
                    order=order,
                    entity_type=AuditLog.EntityType.SERVICE_ORDER,
                    entity_id=order.id,
                    action=AuditLog.Action.ATTACHMENT_ADDED,
                    new_value=f"visibility={attachment.visibility}; file={attachment.original_name}",
                    performed_by=request.user,
                )

                message = "Załącznik został dodany."

        elif action == "update_diagnosis":
            diagnosis = (request.POST.get("diagnosis") or "").strip()
            repair_notes = (request.POST.get("repair_notes") or "").strip()
            final_price_raw = (request.POST.get("final_price") or "").strip().replace(",", ".")

            final_price = None
            if final_price_raw:
                try:
                    final_price = Decimal(final_price_raw)
                except InvalidOperation:
                    error = "Podaj poprawny koszt końcowy."
                else:
                    if final_price < 0:
                        error = "Koszt końcowy nie może być ujemny."

            if error is None:
                old_value = (
                    f"diagnosis={order.diagnosis}; repair_notes={order.repair_notes}; "
                    f"final_price={order.final_price}; accepted={order.customer_accepted_repair}"
                )

                order.diagnosis = diagnosis
                order.repair_notes = repair_notes
                order.final_price = final_price
                order.save()

                new_value = (
                    f"diagnosis={order.diagnosis}; repair_notes={order.repair_notes}; "
                    f"final_price={order.final_price}; accepted={order.customer_accepted_repair}"
                )

                if old_value != new_value:
                    AuditLog.objects.create(
                        order=order,
                        entity_type=AuditLog.EntityType.SERVICE_ORDER,
                        entity_id=order.id,
                        action=AuditLog.Action.DIAGNOSIS_UPDATED,
                        old_value=old_value,
                        new_value=new_value,
                        performed_by=request.user,
                    )

                message = "Diagnoza i rozliczenie zostały zapisane."

        else:
            error = "Nieznana akcja formularza."

    comments_internal = ServiceOrderComment.objects.filter(
        order=order,
        visibility=ServiceOrderComment.Visibility.INTERNAL,
    ).order_by("-created_at")

    comments_public = ServiceOrderComment.objects.filter(
        order=order,
        visibility=ServiceOrderComment.Visibility.PUBLIC,
    ).order_by("-created_at")

    attachments_internal = ServiceOrderAttachment.objects.filter(
        order=order,
        visibility=ServiceOrderAttachment.Visibility.INTERNAL,
    ).order_by("-created_at")

    attachments_public = ServiceOrderAttachment.objects.filter(
        order=order,
        visibility=ServiceOrderAttachment.Visibility.PUBLIC,
    ).order_by("-created_at")

    order_items = order.items.prefetch_related("selected_options").order_by("created_at")

    audit_entries = AuditLog.objects.filter(order=order).order_by("-performed_at")

    return render(
        request,
        "orders/tech_order_detail.html",
        {
            "order": order,
            "comments_internal": comments_internal,
            "comments_public": comments_public,
            "attachments_internal": attachments_internal,
            "attachments_public": attachments_public,
            "order_items": order_items,
            "audit_entries": audit_entries,
            "status_choices": get_available_order_status_choices(order.status),
            "attachment_visibility_choices": ServiceOrderAttachment.Visibility.choices,
            "comment_visibility_choices": ServiceOrderComment.Visibility.choices,
            "est_default": (
                timezone.localtime(order.estimated_completion_at).strftime("%Y-%m-%d %H:%M")
                if order.estimated_completion_at
                else ""
            ),
            "message": message,
            "error": error,
        },
    )
