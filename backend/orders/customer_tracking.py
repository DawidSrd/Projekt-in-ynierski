from .choices import ServiceOrderStatus
from .models import (
    AuditLog,
    ServiceOrderAttachment,
    ServiceOrderComment,
)


STATUS_LABELS = dict(ServiceOrderStatus.choices)

# Klient widzi tylko zdarzenia przydatne w śledzeniu, bez wewnętrznej pracy serwisu.
CUSTOMER_TIMELINE_ACTIONS = [
    AuditLog.Action.ORDER_CREATED,
    AuditLog.Action.STATUS_CHANGED,
    AuditLog.Action.ESTIMATE_SET,
    AuditLog.Action.ORDER_CANCELED,
    AuditLog.Action.DIAGNOSIS_UPDATED,
    AuditLog.Action.REPAIR_ACCEPTED,
]


def build_customer_audit_timeline(order):
    audit_entries = AuditLog.objects.filter(
        order=order,
        action__in=CUSTOMER_TIMELINE_ACTIONS,
    ).order_by("performed_at")

    timeline = []
    for entry in audit_entries:
        if entry.action == AuditLog.Action.ORDER_CREATED:
            timeline.append((entry.performed_at, "Zlecenie przyjęte"))
        elif entry.action == AuditLog.Action.STATUS_CHANGED:
            old_label = STATUS_LABELS.get(entry.old_value, entry.old_value)
            new_label = STATUS_LABELS.get(entry.new_value, entry.new_value)
            timeline.append(
                (entry.performed_at, f"Zmiana statusu: {old_label} → {new_label}")
            )
        elif entry.action == AuditLog.Action.ESTIMATE_SET:
            old_txt = (
                "brak"
                if not entry.old_value or entry.old_value == "None"
                else entry.old_value
            )
            new_txt = (
                "brak"
                if not entry.new_value or entry.new_value == "None"
                else entry.new_value
            )
            timeline.append(
                (entry.performed_at, f"Zmiana planowanego terminu: {old_txt} → {new_txt}")
            )
        elif entry.action == AuditLog.Action.ORDER_CANCELED:
            timeline.append((entry.performed_at, "Zlecenie anulowane"))
        elif entry.action == AuditLog.Action.DIAGNOSIS_UPDATED:
            timeline.append((entry.performed_at, "Aktualizacja diagnozy i rozliczenia"))
        elif entry.action == AuditLog.Action.REPAIR_ACCEPTED:
            timeline.append((entry.performed_at, "Klient zaakceptował naprawę"))

    return timeline


def build_customer_tracking_result(order, email, phone):
    # Do odpowiedzi trafiają tylko komentarze i załączniki oznaczone jako publiczne.
    public_comments = ServiceOrderComment.objects.filter(
        order=order,
        visibility=ServiceOrderComment.Visibility.PUBLIC,
    ).order_by("created_at")

    public_attachments = ServiceOrderAttachment.objects.filter(
        order=order,
        visibility=ServiceOrderAttachment.Visibility.PUBLIC,
    ).order_by("created_at")

    order_items = order.items.prefetch_related("selected_options").order_by("created_at")

    return {
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
        "has_final_price": order.final_price is not None,
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
        "order_items": order_items,
        "audit_timeline": build_customer_audit_timeline(order),
        "can_cancel": order.can_cancel(),
        "email": email,
        "phone": phone,
    }
