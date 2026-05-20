from .models import AuditLog


def format_service_result(order):
    return (
        f"diagnosis={order.diagnosis}; repair_notes={order.repair_notes}; "
        f"final_price={order.final_price}; accepted={order.customer_accepted_repair}"
    )


def log_order_created(order, performed_by=None):
    return AuditLog.objects.create(
        order=order,
        entity_type=AuditLog.EntityType.SERVICE_ORDER,
        entity_id=order.id,
        action=AuditLog.Action.ORDER_CREATED,
        new_value=f"status={order.status}",
        performed_by=performed_by,
    )


def log_order_canceled(order, old_status, performed_by=None):
    return AuditLog.objects.create(
        order=order,
        entity_type=AuditLog.EntityType.SERVICE_ORDER,
        entity_id=order.id,
        action=AuditLog.Action.ORDER_CANCELED,
        old_value=old_status,
        new_value=order.status,
        performed_by=performed_by,
    )


def log_status_changed(order, old_status, performed_by=None):
    return AuditLog.objects.create(
        order=order,
        entity_type=AuditLog.EntityType.SERVICE_ORDER,
        entity_id=order.id,
        action=AuditLog.Action.STATUS_CHANGED,
        old_value=old_status,
        new_value=order.status,
        performed_by=performed_by,
    )


def log_estimate_set(order, old_estimate, performed_by=None):
    return AuditLog.objects.create(
        order=order,
        entity_type=AuditLog.EntityType.SERVICE_ORDER,
        entity_id=order.id,
        action=AuditLog.Action.ESTIMATE_SET,
        old_value=str(old_estimate),
        new_value=str(order.estimated_completion_at),
        performed_by=performed_by,
    )


def log_repair_accepted(order, performed_by=None):
    return AuditLog.objects.create(
        order=order,
        entity_type=AuditLog.EntityType.SERVICE_ORDER,
        entity_id=order.id,
        action=AuditLog.Action.REPAIR_ACCEPTED,
        old_value="False",
        new_value="True",
        performed_by=performed_by,
    )


def log_technician_assigned(order, old_technician=None, new_technician=None, performed_by=None):
    return AuditLog.objects.create(
        order=order,
        entity_type=AuditLog.EntityType.SERVICE_ORDER,
        entity_id=order.id,
        action=AuditLog.Action.TECHNICIAN_ASSIGNED,
        old_value=getattr(old_technician, "username", old_technician) or "",
        new_value=getattr(new_technician, "username", new_technician) or "",
        performed_by=performed_by,
    )


def log_comment_added(comment, performed_by=None):
    return AuditLog.objects.create(
        order=comment.order,
        entity_type=AuditLog.EntityType.SERVICE_ORDER_COMMENT,
        entity_id=comment.id,
        action=AuditLog.Action.COMMENT_ADDED,
        new_value=f"visibility={comment.visibility}",
        performed_by=performed_by,
    )


def log_attachment_added(attachment, performed_by=None):
    return AuditLog.objects.create(
        order=attachment.order,
        entity_type=AuditLog.EntityType.SERVICE_ORDER,
        entity_id=attachment.order_id,
        action=AuditLog.Action.ATTACHMENT_ADDED,
        new_value=f"visibility={attachment.visibility}; file={attachment.original_name}",
        performed_by=performed_by,
    )


def log_diagnosis_updated(order, old_value, performed_by=None):
    return AuditLog.objects.create(
        order=order,
        entity_type=AuditLog.EntityType.SERVICE_ORDER,
        entity_id=order.id,
        action=AuditLog.Action.DIAGNOSIS_UPDATED,
        old_value=old_value,
        new_value=format_service_result(order),
        performed_by=performed_by,
    )
