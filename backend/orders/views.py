from django.shortcuts import render
from .models import Service, ServiceOptionGroup, ServiceOption
from .models import ServiceOrder, ServiceOrderComment, ServiceOrderItem, ServiceOrderItemOption
from django.core.mail import send_mail
from .models import AuditLog
from django.shortcuts import redirect
from .choices import ServiceOrderStatus


STATUS_LABELS = dict(ServiceOrderStatus.choices)



def track_order(request):
    """
    Guest access: śledzenie zlecenia bez logowania.

    GET  -> pokazuje formularz
    POST -> weryfikuje dane i pokazuje wynik
    """
    context = {"result": None, "error": None}

    if request.method == "POST":
        order_number = (request.POST.get("order_number") or "").strip().upper()
        email = (request.POST.get("email") or "").strip().lower()
        phone = (request.POST.get("phone") or "").strip()

        # Minimalne wymaganie: numer zlecenia + (email albo phone)
        if not order_number or (not email and not phone):
            context["error"] = "Podaj numer zlecenia oraz e-mail lub numer telefonu."
            return render(request, "orders/track_order.html", context)

        # Szukamy zlecenia
        order = ServiceOrder.objects.filter(order_number=order_number).first()

        # Bezpieczeństwo: nie mówimy, czy numer jest poprawny.
        if not order:
            context["error"] = "Nie znaleziono zlecenia dla podanych danych."
            return render(request, "orders/track_order.html", context)

        # Weryfikacja: email lub telefon musi pasować do zlecenia
        email_ok = email and (order.customer_email.lower() == email)
        phone_ok = phone and (order.customer_phone == phone)

        if not (email_ok or phone_ok):
            context["error"] = "Nie znaleziono zlecenia dla podanych danych."
            return render(request, "orders/track_order.html", context)

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





        context["result"] = {
            "status_labels": STATUS_LABELS,
            "order_number": order.order_number,
            "status": order.get_status_display(),
            "estimated_completion_at": order.estimated_completion_at,
            "comments": public_comments,
            "audit_entries": audit_entries,
            "audit_timeline": audit_timeline,
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
    service = Service.objects.get(pk=service_id, is_active=True)

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
    }

    if request.method == "POST":

        customer_defaults = {
            "customer_name": request.POST.get("customer_name", ""),
            "customer_email": request.POST.get("customer_email", ""),
            "customer_phone": request.POST.get("customer_phone", ""),
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

        selected_options = ServiceOption.objects.filter(id__in=selected_option_ids)

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
            customer_email = (request.POST.get("customer_email") or "").strip()
            customer_phone = (request.POST.get("customer_phone") or "").strip()

            if not customer_name or not customer_email or not customer_phone:
                result["error"] = "Uzupełnij dane kontaktowe, aby utworzyć zlecenie."
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
        {"order_number": order_number},
    )

