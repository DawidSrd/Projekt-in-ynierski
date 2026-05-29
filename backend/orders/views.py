from django.http import FileResponse, Http404
from django.db.models import Case, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from .models import (
    Service,
    ServiceOrder,
    ServiceOrderAttachment,
    ServiceOrderComment,
)
from .models import AuditLog
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from .choices import (
    ServiceOrderStatus,
    get_available_order_status_choices,
)
from .customer_tracking import build_customer_tracking_result
from .services import (
    accept_customer_repair,
    add_order_attachment,
    add_order_comment,
    cancel_customer_order,
    claim_order_for_technician,
    create_configured_order,
    create_staff_order,
    get_configurator_selection,
    get_customer_defaults,
    get_service_group_options,
    update_order_diagnosis,
    update_order_status,
)
from .validators import normalize_phone_number



STATUS_LABELS = dict(ServiceOrderStatus.choices)


def redirect_staff_from_client_area(request):
    if request.user.is_staff:
        return redirect("tech_dashboard")
    return None


def home(request):
    staff_redirect = redirect_staff_from_client_area(request)
    if staff_redirect:
        return staff_redirect

    services = Service.objects.filter(
        is_active=True,
        pricing_mode=Service.PricingMode.CONFIGURABLE,
    ).order_by("id")[:4]

    return render(request, "orders/home.html", {"services": services})


def about(request):
    staff_redirect = redirect_staff_from_client_area(request)
    if staff_redirect:
        return staff_redirect

    return render(request, "orders/about.html")


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
            message, error = cancel_customer_order(order)
            context["message"] = message
            context["error"] = error

        elif action == "accept_repair":
            message, error = accept_customer_repair(order)
            context["message"] = message
            context["error"] = error

        context["result"] = build_customer_tracking_result(order, email, phone)

    return render(request, "orders/track_order.html", context)


def service_catalog(request):
    """
    Katalog usług dla klienta (read-only).
    Pokazuje tylko aktywne usługi.
    """
    staff_redirect = redirect_staff_from_client_area(request)
    if staff_redirect:
        return staff_redirect

    services = (
        Service.objects.filter(is_active=True)
        .annotate(
            catalog_order=Case(
                When(
                    pricing_mode=Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
                    then=Value(0),
                ),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("catalog_order", "id")
    )

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

    group_options = get_service_group_options(service)

    result = None
    selected_option_ids = set()

    customer_defaults = get_customer_defaults()

    if request.method == "POST":

        customer_defaults = get_customer_defaults(request.POST)
        selection = get_configurator_selection(service, group_options, request.POST)
        result = selection["result"]
        selected_option_ids = selection["selected_option_ids"]

        action = request.POST.get("action")

        if action == "create_order":
            order, error, email_status = create_configured_order(
                service,
                selection["selected_options"],
                selection["total_min"],
                selection["total_max"],
                request.POST,
                request.FILES.get("attachment"),
                selection["required_option_errors"],
            )

            if error:
                result["error"] = error
            else:
                request.session[f"order_created_email_status_{order.order_number}"] = (
                    email_status
                )

                return redirect("order_created", order_number=order.order_number)

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
    Dashboard technika: podział zleceń na Nowe / W toku / przekroczone terminy.
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
def tech_order_create(request):
    """
    Tworzenie zlecenia przez pracownika podczas przyjęcia sprzętu w serwisie.
    """
    services = Service.objects.filter(is_active=True).order_by("id")
    error = None
    email_status = None
    form_defaults = get_customer_defaults(request.POST if request.method == "POST" else None)
    selected_service_id = (request.POST.get("service_id") or "") if request.method == "POST" else ""
    notify_customer = request.method != "POST" or request.POST.get("notify_customer") == "on"

    if request.method == "POST":
        order, error, email_status = create_staff_order(request.POST, request.user)
        if order and not error:
            return redirect(f"/tech/orders/{order.order_number}/?created=1&email_status={email_status}")

    return render(
        request,
        "orders/tech_order_create.html",
        {
            "device_type_choices": ServiceOrder.DeviceType.choices,
            "email_status": email_status,
            "error": error,
            "form_defaults": form_defaults,
            "notify_customer": notify_customer,
            "selected_service_id": selected_service_id,
            "services": services,
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

    if request.GET.get("created") == "1":
        email_status = request.GET.get("email_status")
        if email_status == "sent":
            message = "Zlecenie zostało utworzone i wysłano potwierdzenie e-mail do klienta."
        elif email_status == "failed":
            message = "Zlecenie zostało utworzone, ale nie udało się wysłać potwierdzenia e-mail."
        else:
            message = "Zlecenie zostało utworzone."

    if request.method == "POST":
        action = request.POST.get("action") or "update_order"

        if action == "claim_order":
            message, error = claim_order_for_technician(order, request.user)

        elif action == "update_order":
            new_status = request.POST.get("status")
            estimate_raw = (request.POST.get("estimated_completion_at") or "").strip()
            notify_customer = request.POST.get("notify_customer") == "on"
            message, error = update_order_status(
                order,
                request.user,
                new_status,
                estimate_raw,
                notify_customer,
            )

        elif action == "add_comment":
            visibility = request.POST.get("visibility")
            content = (request.POST.get("content") or "").strip()
            message, error = add_order_comment(order, request.user, visibility, content)

        elif action == "add_attachment":
            visibility = request.POST.get("visibility")
            uploaded_file = request.FILES.get("file")
            message, error = add_order_attachment(
                order,
                request.user,
                visibility,
                uploaded_file,
            )

        elif action == "update_diagnosis":
            diagnosis = (request.POST.get("diagnosis") or "").strip()
            repair_notes = (request.POST.get("repair_notes") or "").strip()
            final_price_raw = (request.POST.get("final_price") or "").strip().replace(",", ".")
            message, error = update_order_diagnosis(
                order,
                request.user,
                diagnosis,
                repair_notes,
                final_price_raw,
            )

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
                timezone.localtime(order.estimated_completion_at).strftime("%Y-%m-%dT%H:%M")
                if order.estimated_completion_at
                else ""
            ),
            "message": message,
            "error": error,
        },
    )
