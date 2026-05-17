from django import template
from django.utils import timezone

from orders.choices import ServiceOrderStatus
from orders.models import ServiceOrder


register = template.Library()


@register.simple_tag
def admin_dashboard_stats():
    active_orders = ServiceOrder.objects.exclude(
        status__in=[ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELED]
    )
    recent_orders = ServiceOrder.objects.select_related("assigned_technician").order_by("-created_at")[:6]

    return {
        "active": active_orders.count(),
        "new": ServiceOrder.objects.filter(status=ServiceOrderStatus.NEW).count(),
        "overdue": active_orders.filter(estimated_completion_at__lt=timezone.now()).count(),
        "completed": ServiceOrder.objects.filter(status=ServiceOrderStatus.COMPLETED).count(),
        "unassigned": active_orders.filter(assigned_technician__isnull=True).count(),
        "awaiting_acceptance": active_orders.filter(
            diagnosis__gt="",
            final_price__isnull=False,
            customer_accepted_repair=False,
        ).count(),
        "recent_orders": recent_orders,
    }
