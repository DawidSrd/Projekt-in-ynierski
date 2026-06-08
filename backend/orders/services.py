from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .audit import (
    format_service_result,
    log_attachment_added,
    log_comment_added,
    log_diagnosis_updated,
    log_estimate_set,
    log_order_canceled,
    log_order_created,
    log_repair_accepted,
    log_status_changed,
    log_technician_assigned,
)
from .choices import ServiceOrderStatus, can_change_order_status
from .models import (
    Service,
    ServiceOption,
    ServiceOptionGroup,
    ServiceOrder,
    ServiceOrderAttachment,
    ServiceOrderComment,
    ServiceOrderItem,
    ServiceOrderItemOption,
)
from .validators import (
    get_attachment_error,
    get_customer_order_errors,
    get_device_order_errors,
)


def get_customer_defaults(data=None):
    data = data or {}
    return {
        "customer_name": data.get("customer_name", ""),
        "customer_email": data.get("customer_email", ""),
        "customer_phone": data.get("customer_phone", ""),
        "customer_consent": data.get("customer_consent") == "on",
        "device_type": data.get("device_type", ""),
        "device_brand": data.get("device_brand", ""),
        "device_model": data.get("device_model", ""),
        "device_issue_description": data.get("device_issue_description", ""),
    }


def get_service_group_options(service):
    groups = ServiceOptionGroup.objects.filter(
        service=service,
        is_active=True,
    ).order_by("sort_order", "id")

    return [
        (
            group,
            ServiceOption.objects.filter(
                group=group,
                is_active=True,
            ).order_by("sort_order", "id"),
        )
        for group in groups
    ]


def get_configurator_selection(service, group_options, data):
    posted_option_ids = []

    for group, _options in group_options:
        field_name = f"group_{group.id}"

        if group.selection_type == ServiceOptionGroup.SelectionType.SINGLE:
            chosen = data.get(field_name)
            if chosen:
                try:
                    posted_option_ids.append(int(chosen))
                except ValueError:
                    pass
        else:
            for chosen in data.getlist(field_name):
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
    selected_group_ids = {option.group_id for option in selected_options}
    required_option_errors = [
        f'Wybierz opcję w grupie "{group.name}".'
        for group, _options in group_options
        if group.is_required and group.id not in selected_group_ids
    ]

    total_min = service.base_price_min
    total_max = service.base_price_max
    total_duration_minutes = service.base_duration_minutes

    for option in selected_options:
        total_min += option.price_delta_min
        total_max += option.price_delta_max
        total_duration_minutes += option.duration_delta_minutes

    result = {
        "has_price": not required_option_errors and not service.requires_manual_pricing,
        "total_min": total_min,
        "total_max": total_max,
        "total_duration_minutes": max(total_duration_minutes, 0),
        "selected_options": selected_options,
    }
    if required_option_errors:
        result["error"] = " ".join(required_option_errors)

    return {
        "required_option_errors": required_option_errors,
        "result": result,
        "selected_option_ids": {option.id for option in selected_options},
        "selected_options": selected_options,
        "total_min": total_min,
        "total_max": total_max,
    }


def create_configured_order(service, selected_options, total_min, total_max, data, uploaded_file, required_option_errors):
    customer_name = (data.get("customer_name") or "").strip()
    customer_email = (data.get("customer_email") or "").strip().lower()
    customer_phone = (data.get("customer_phone") or "").strip()
    customer_consent = data.get("customer_consent") == "on"
    device_type = (data.get("device_type") or "").strip()
    device_brand = (data.get("device_brand") or "").strip()
    device_model = (data.get("device_model") or "").strip()
    device_issue_description = (data.get("device_issue_description") or "").strip()

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
        return None, " ".join(
            [
                *required_option_errors,
                *customer_errors,
                *device_errors,
                *([attachment_error] if attachment_error else []),
            ]
        )

    # Transakcja chroni przed zleceniem bez zapisanej pozycji wyceny.
    with transaction.atomic():
        order = ServiceOrder.objects.create(
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            device_type=device_type,
            device_brand=device_brand,
            device_model=device_model,
            device_issue_description=device_issue_description,
        )
        log_order_created(order)

        if uploaded_file:
            attachment = ServiceOrderAttachment.objects.create(
                order=order,
                visibility=ServiceOrderAttachment.Visibility.PUBLIC,
                file=uploaded_file,
                original_name=uploaded_file.name,
                uploaded_by=None,
            )
            log_attachment_added(attachment)

        order_item = ServiceOrderItem.objects.create(
            order=order,
            service=service,
            service_name_snapshot=service.name,
            pricing_mode_snapshot=service.pricing_mode,
            base_price_min_snapshot=service.base_price_min,
            base_price_max_snapshot=service.base_price_max,
            calculated_price_min=total_min,
            calculated_price_max=total_max,
        )

        for option in selected_options:
            ServiceOrderItemOption.objects.create(
                order_item=order_item,
                option=option,
                option_name_snapshot=option.name,
                price_delta_min_snapshot=option.price_delta_min,
                price_delta_max_snapshot=option.price_delta_max,
            )

    return order, None


def create_staff_order(data, user):
    service_id = data.get("service_id")
    customer_name = (data.get("customer_name") or "").strip()
    customer_email = (data.get("customer_email") or "").strip().lower()
    customer_phone = (data.get("customer_phone") or "").strip()
    device_type = (data.get("device_type") or "").strip()
    device_brand = (data.get("device_brand") or "").strip()
    device_model = (data.get("device_model") or "").strip()
    device_issue_description = (data.get("device_issue_description") or "").strip()
    # Przyjęcie sprzętu w punkcie wymaga danych kontaktowych do obsługi zlecenia,
    # dlatego nie zbieramy tu dodatkowej zgody na kontakt.
    customer_errors = get_customer_order_errors(
        customer_name,
        customer_email,
        customer_phone,
        True,
    )
    device_errors = get_device_order_errors(
        device_type,
        device_brand,
        device_issue_description,
    )

    try:
        service = Service.objects.get(pk=service_id, is_active=True)
    except (Service.DoesNotExist, ValueError, TypeError):
        service = None

    service_errors = []
    if service is None:
        service_errors.append("Wybierz usługę z katalogu.")

    if customer_errors or device_errors or service_errors:
        return None, " ".join([*service_errors, *customer_errors, *device_errors])

    calculated_min = service.base_price_min
    calculated_max = service.base_price_max
    if service.requires_manual_pricing:
        calculated_min = 0
        calculated_max = 0

    # Przyjęcie w punkcie od razu przypisuje zlecenie do pracownika i oznacza je jako przyjęte.
    with transaction.atomic():
        order = ServiceOrder.objects.create(
            customer_name=customer_name,
            customer_email=customer_email,
            customer_phone=customer_phone,
            device_type=device_type,
            device_brand=device_brand,
            device_model=device_model,
            device_issue_description=device_issue_description,
            status=ServiceOrderStatus.RECEIVED,
            assigned_technician=user,
        )
        log_order_created(order, user)
        log_technician_assigned(order, new_technician=user, performed_by=user)

        ServiceOrderItem.objects.create(
            order=order,
            service=service,
            service_name_snapshot=service.name,
            pricing_mode_snapshot=service.pricing_mode,
            base_price_min_snapshot=service.base_price_min,
            base_price_max_snapshot=service.base_price_max,
            calculated_price_min=calculated_min,
            calculated_price_max=calculated_max,
        )

    return order, None


def cancel_customer_order(order):
    if not order.can_cancel():
        return None, (
            "Anulowanie online jest dostępne tylko dla nowych zleceń. "
            "Skontaktuj się telefonicznie z serwisem."
        )

    old_status = order.status
    order.status = ServiceOrderStatus.CANCELED
    order.save()
    log_order_canceled(order, old_status)

    return "Zlecenie zostało anulowane.", None


def accept_customer_repair(order, performed_by=None):
    if order.can_accept_repair():
        order.customer_accepted_repair = True
        order.save()
        log_repair_accepted(order, performed_by)
        if performed_by:
            return "Zgoda klienta została zarejestrowana.", None
        return "Naprawa została zaakceptowana.", None

    if order.customer_accepted_repair:
        return "Naprawa została już zaakceptowana.", None

    return None, "Akceptacja naprawy nie jest jeszcze dostępna."


def claim_order_for_technician(order, user):
    if order.assigned_technician is None:
        claimed = ServiceOrder.objects.filter(
            pk=order.pk,
            assigned_technician__isnull=True,
        ).update(
            assigned_technician=user,
            updated_at=timezone.now(),
        )
        order.refresh_from_db()

        if claimed:
            log_technician_assigned(order, new_technician=user, performed_by=user)
            return "Zlecenie zostało przypisane do Ciebie.", None

        if order.assigned_technician == user:
            return "To zlecenie jest już przypisane do Ciebie.", None

        return None, "Zlecenie jest już przypisane do innego technika."

    if order.assigned_technician == user:
        return "To zlecenie jest już przypisane do Ciebie.", None

    return None, "Zlecenie jest już przypisane do innego technika."


def update_order_status(order, user, new_status, estimate_raw):
    old_status = order.status
    old_estimate = order.estimated_completion_at

    if new_status not in dict(ServiceOrderStatus.choices):
        return None, "Wybrano nieprawidłowy status."

    if not can_change_order_status(order.status, new_status):
        return None, "Taka zmiana statusu nie jest dozwolona w aktualnym etapie obsługi."

    new_estimate = None
    if estimate_raw:
        parsed = parse_datetime(estimate_raw.replace(" ", "T"))
        if parsed is None:
            return None, "Nieprawidłowy format planowanego terminu."

        new_estimate = parsed
        if timezone.is_naive(new_estimate):
            new_estimate = timezone.make_aware(new_estimate)

    order.status = new_status
    order.estimated_completion_at = new_estimate
    order.save()

    if old_status != order.status:
        log_status_changed(order, old_status, user)

    if old_estimate != order.estimated_completion_at:
        log_estimate_set(order, old_estimate, user)

    return "Zlecenie zostało zaktualizowane.", None


def add_order_comment(order, user, visibility, content):
    if visibility not in dict(ServiceOrderComment.Visibility.choices):
        return None, "Wybrano nieprawidłowy typ komentarza."

    if not content:
        return None, "Treść komentarza nie może być pusta."

    comment = ServiceOrderComment.objects.create(
        order=order,
        created_by=user,
        visibility=visibility,
        content=content,
    )
    log_comment_added(comment, user)

    return "Komentarz został dodany.", None


def add_order_attachment(order, user, visibility, uploaded_file):
    attachment_error = get_attachment_error(uploaded_file)

    if visibility not in dict(ServiceOrderAttachment.Visibility.choices):
        return None, "Wybrano nieprawidłowy typ załącznika."

    if attachment_error:
        return None, attachment_error

    attachment = ServiceOrderAttachment.objects.create(
        order=order,
        visibility=visibility,
        file=uploaded_file,
        original_name=uploaded_file.name,
        uploaded_by=user,
    )
    log_attachment_added(attachment, user)

    return "Załącznik został dodany.", None


def update_order_diagnosis(order, user, diagnosis, repair_notes, final_price_raw):
    final_price = None

    if final_price_raw:
        try:
            final_price = Decimal(final_price_raw)
        except InvalidOperation:
            return None, "Podaj poprawny koszt końcowy."

        if final_price < 0:
            return None, "Koszt końcowy nie może być ujemny."

    # Porównanie stanu przed i po zmianie chroni historię przed pustymi wpisami.
    old_value = format_service_result(order)
    order.diagnosis = diagnosis
    order.repair_notes = repair_notes
    order.final_price = final_price
    order.save()

    if old_value != format_service_result(order):
        log_diagnosis_updated(order, old_value, user)

    return "Diagnoza i rozliczenie zostały zapisane.", None
