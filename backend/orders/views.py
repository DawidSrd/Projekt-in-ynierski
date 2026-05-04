import re

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from .models import Service, ServiceOptionGroup, ServiceOption
from .models import ServiceOrder, ServiceOrderComment, ServiceOrderItem, ServiceOrderItemOption
from django.core.mail import send_mail
from django.core.validators import validate_email
from .models import AuditLog
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



STATUS_LABELS = dict(ServiceOrderStatus.choices)
PHONE_PATTERN = re.compile(r"^\+?[0-9\s-]{7,20}$")


def get_customer_order_errors(customer_name, customer_email, customer_phone, customer_consent):
    errors = []

    if len(customer_name) < 3 or any(char.isdigit() for char in customer_name):
        errors.append("Podaj poprawne imię i nazwisko.")

    try:
        validate_email(customer_email)
    except ValidationError:
        errors.append("Podaj poprawny adres e-mail.")

    phone_digits = re.sub(r"\D", "", customer_phone)
    if not PHONE_PATTERN.match(customer_phone) or len(phone_digits) < 7 or len(phone_digits) > 15:
        errors.append("Podaj poprawny numer telefonu.")

    if not customer_consent:
        errors.append("Potwierdź zgodę na kontakt w sprawie zlecenia.")

    return errors


def home(request):
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
    phone_ok = phone and (order.customer_phone == phone)

    if not (email_ok or phone_ok):
        return None

    return order


def track_order(request):
    """
    Guest access: śledzenie zlecenia bez logowania.

    GET  -> pokazuje formularz
    POST -> weryfikuje dane i pokazuje wynik
    """
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

                send_mail(
                    subject=f"Anulowanie zlecenia {order.order_number}",
                    message=(
                        f"Twoje zlecenie {order.order_number} zostało anulowane.\n\n"
                        f"Aktualny status: {order.get_status_display()}\n"
                    ),
                    from_email=None,
                    recipient_list=[order.customer_email],
                )

                context["message"] = "Zlecenie zostało anulowane."
            else:
                context["error"] = (
                    "Anulowanie online jest dostępne tylko dla nowych zleceń. "
                    "Skontaktuj się telefonicznie z serwisem."
                )

        public_comments = ServiceOrderComment.objects.filter(
            order=order,
            visibility=ServiceOrderComment.Visibility.PUBLIC,
        ).order_by("created_at")

        audit_entries = AuditLog.objects.filter(
            order=order,
            action__in=[
                AuditLog.Action.ORDER_CREATED,
                AuditLog.Action.STATUS_CHANGED,
                AuditLog.Action.ESTIMATE_SET,
                AuditLog.Action.ORDER_CANCELED,
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





        context["result"] = {
            "status_labels": STATUS_LABELS,
            "order_number": order.order_number,
            "status": order.get_status_display(),
            "estimated_completion_at": order.estimated_completion_at,
            "comments": public_comments,
            "audit_entries": audit_entries,
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

    customer_defaults = {
        "customer_name": "",
        "customer_email": "",
        "customer_phone": "",
        "customer_consent": False,
    }

    if request.method == "POST":

        customer_defaults = {
            "customer_name": request.POST.get("customer_name", ""),
            "customer_email": request.POST.get("customer_email", ""),
            "customer_phone": request.POST.get("customer_phone", ""),
            "customer_consent": request.POST.get("customer_consent") == "on",
        }

        # Zbieramy zaznaczone opcje z formularza
        selected_option_ids = []

        for g, _opts in group_options:
            field_name = f"group_{g.id}"

            if g.selection_type == ServiceOptionGroup.SelectionType.SINGLE:
                chosen = request.POST.get(field_name)
                if chosen:
                    selected_option_ids.append(int(chosen))
            else:
                chosen_list = request.POST.getlist(field_name)
                selected_option_ids.extend([int(x) for x in chosen_list if x])

        selected_options = ServiceOption.objects.filter(
            id__in=selected_option_ids,
            group__service=service,
            group__is_active=True,
            is_active=True,
        )

        # Liczymy widełki ceny: baza + sumy delt
        total_min = service.base_price_min
        total_max = service.base_price_max

        for opt in selected_options:
            total_min += opt.price_delta_min
            total_max += opt.price_delta_max

        result = {
            "total_min": total_min,
            "total_max": total_max,
            "selected_options": selected_options,
        }
        action = request.POST.get("action")

        if action == "create_order":
            customer_name = (request.POST.get("customer_name") or "").strip()
            customer_email = (request.POST.get("customer_email") or "").strip().lower()
            customer_phone = (request.POST.get("customer_phone") or "").strip()
            customer_consent = request.POST.get("customer_consent") == "on"
            customer_errors = get_customer_order_errors(
                customer_name,
                customer_email,
                customer_phone,
                customer_consent,
            )

            if customer_errors:
                result["error"] = " ".join(customer_errors)
            else:
                order = ServiceOrder.objects.create(
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                )

                AuditLog.objects.create(
                    order=order,
                    entity_type=AuditLog.EntityType.SERVICE_ORDER,
                    entity_id=order.id,
                    action=AuditLog.Action.ORDER_CREATED,
                    new_value=f"status={order.status}",
                    performed_by=None,
                )

                send_mail(
                    subject=f"Potwierdzenie przyjęcia zlecenia {order.order_number}",
                    message=(
                        f"Dziękujemy! Twoje zlecenie zostało przyjęte.\n\n"
                        f"Numer zlecenia: {order.order_number}\n"
                        f"Status: {order.get_status_display()}\n\n"
                        f"Możesz śledzić status tutaj: /track/\n"
                        f"(podaj numer zlecenia oraz e-mail lub telefon)\n"
                    ),
                    from_email=None,
                    recipient_list=[order.customer_email],
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

                return redirect("order_created", order_number=order.order_number)
            customer_defaults = {
                "customer_name": request.POST.get("customer_name", "") if request.method == "POST" else "",
                "customer_email": request.POST.get("customer_email", "") if request.method == "POST" else "",
                "customer_phone": request.POST.get("customer_phone", "") if request.method == "POST" else "",
                "customer_consent": request.POST.get("customer_consent") == "on",
            }

    return render(
        request,
        "orders/service_configurator.html",
        {
            "service": service,
            "group_options": group_options,
            "result": result,
            "customer_defaults": customer_defaults,
        },
    )


def order_created(request, order_number: str):
    """
    Strona potwierdzenia utworzenia zlecenia (GET).
    """
    return render(
        request,
        "orders/order_created.html",
        {
            "order_number": order_number,
            "track_url": f"/track/?order_number={order_number}",
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

    orders_new = ServiceOrder.objects.filter(status=ServiceOrderStatus.NEW).order_by("-created_at")

    orders_in_progress = ServiceOrder.objects.filter(
        status__in=[
            ServiceOrderStatus.RECEIVED,
            ServiceOrderStatus.IN_PROGRESS,
            ServiceOrderStatus.WAITING_FOR_PARTS,
        ]
    ).order_by("-created_at")

    orders_ready = ServiceOrder.objects.filter(status=ServiceOrderStatus.READY).order_by("-created_at")

    filtered_orders = ServiceOrder.objects.none()
    selected_status_label = None
    if selected_status:
        filtered_orders = ServiceOrder.objects.filter(status=selected_status).order_by("-created_at")
        selected_status_label = STATUS_LABELS[selected_status]

    dashboard_counts = {
        "new": orders_new.count(),
        "in_progress": orders_in_progress.count(),
        "ready": orders_ready.count(),
        "active": ServiceOrder.objects.exclude(
            status__in=[ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELED]
        ).count(),
        "completed": ServiceOrder.objects.filter(status=ServiceOrderStatus.COMPLETED).count(),
    }

    all_active = ServiceOrder.objects.exclude(
        status__in=[ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELED]
    ).order_by("-created_at")
    orders_overdue = [o for o in all_active if o.is_overdue()]
    dashboard_counts["overdue"] = len(orders_overdue)

    if selected_status:
        dashboard_orders = list(filtered_orders)
    else:
        status_priority = {
            ServiceOrderStatus.NEW: 1,
            ServiceOrderStatus.IN_PROGRESS: 2,
            ServiceOrderStatus.WAITING_FOR_PARTS: 3,
            ServiceOrderStatus.RECEIVED: 4,
            ServiceOrderStatus.READY: 5,
        }
        dashboard_orders = sorted(
            all_active,
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
            "filtered_orders": filtered_orders,
            "orders_new": orders_new,
            "orders_in_progress": orders_in_progress,
            "orders_overdue": orders_overdue,
            "orders_ready": orders_ready,
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

        if action == "update_order":
            new_status = request.POST.get("status")
            estimate_raw = (request.POST.get("estimated_completion_at") or "").strip()
            notify_customer = request.POST.get("notify_customer") == "on"

            old_status = order.status
            old_estimate = order.estimated_completion_at

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
                            send_mail(
                                subject=f"Zmiana statusu zlecenia {order.order_number}",
                                message=(
                                    f"Status Twojego zlecenia {order.order_number} został zmieniony.\n\n"
                                    f"Aktualny status: {order.get_status_display()}\n"
                                ),
                                from_email=None,
                                recipient_list=[order.customer_email],
                            )

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

                    if notify_customer and old_status != order.status:
                        message = "Zlecenie zostało zaktualizowane, a klient otrzymał wiadomość e-mail."
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

    order_items = order.items.prefetch_related("selected_options").order_by("created_at")

    audit_entries = AuditLog.objects.filter(order=order).order_by("-performed_at")

    return render(
        request,
        "orders/tech_order_detail.html",
        {
            "order": order,
            "comments_internal": comments_internal,
            "comments_public": comments_public,
            "order_items": order_items,
            "audit_entries": audit_entries,
            "status_choices": get_available_order_status_choices(order.status),
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
