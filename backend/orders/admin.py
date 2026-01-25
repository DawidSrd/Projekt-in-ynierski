from django.contrib import admin
from .models import Service, ServiceOptionGroup, ServiceOption, ServiceOrder
from .models import ServiceOrderComment
from .models import AuditLog
from .models import ServiceOrder, AuditLog


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "base_price_min", "base_price_max", "base_duration_minutes", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(ServiceOptionGroup)
class ServiceOptionGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "service", "selection_type", "is_required", "is_active", "sort_order")
    list_filter = ("selection_type", "is_required", "is_active")
    search_fields = ("name", "service__name")


@admin.register(ServiceOption)
class ServiceOptionAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "price_delta_min", "price_delta_max", "duration_delta_minutes", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "group__name", "group__service__name")

class ServiceOrderCommentInline(admin.TabularInline):
    model = ServiceOrderComment
    extra = 1
    fields = ("visibility", "content", "created_at")
    readonly_fields = ("created_at",)

class AuditLogInline(admin.TabularInline):
    model = AuditLog
    extra = 0
    fields = ("action", "performed_by", "performed_at", "old_value", "new_value")
    readonly_fields = ("action", "performed_by", "performed_at", "old_value", "new_value")
    can_delete = False


@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer_name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("order_number", "customer_name", "customer_email", "customer_phone")
    inlines = [ServiceOrderCommentInline, AuditLogInline]

    def save_model(self, request, obj, form, change):
        """
        Hook Django Admin wywoływany przy zapisie zlecenia.
        """
        old_status = None
        old_estimate = None

        if change:
            old_obj = ServiceOrder.objects.get(pk=obj.pk)
            old_status = old_obj.status
            old_estimate = old_obj.estimated_completion_at

        super().save_model(request, obj, form, change)

        if not change:
            AuditLog.objects.create(
                order=obj,
                entity_type=AuditLog.EntityType.SERVICE_ORDER,
                entity_id=obj.id,
                action=AuditLog.Action.ORDER_CREATED,
                new_value=f"status={obj.status}",
                performed_by=request.user,
            )
            return

        if old_status != obj.status:
            AuditLog.objects.create(
                order=obj,
                entity_type=AuditLog.EntityType.SERVICE_ORDER,
                entity_id=obj.id,
                action=AuditLog.Action.STATUS_CHANGED,
                old_value=old_status,
                new_value=obj.status,
                performed_by=request.user,
            )

        if old_estimate != obj.estimated_completion_at:
            AuditLog.objects.create(
                order=obj,
                entity_type=AuditLog.EntityType.SERVICE_ORDER,
                entity_id=obj.id,
                action=AuditLog.Action.ESTIMATE_SET,
                old_value=str(old_estimate),
                new_value=str(obj.estimated_completion_at),
                performed_by=request.user,
            )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("entity_type", "entity_id", "action", "performed_by", "performed_at")
    list_filter = ("entity_type", "action")
    search_fields = ("entity_type", "entity_id", "old_value", "new_value", "performed_by__username")
    readonly_fields = ("entity_type", "entity_id", "action", "old_value", "new_value", "performed_by", "performed_at", "order")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


def save_model(self, request, obj, form, change):
    """
    Hook admina wywoływany przy zapisie obiektu w panelu.
    change=False oznacza tworzenie, change=True oznacza edycję.
    """
    # Jeżeli to edycja, pobieramy poprzedni stan z bazy, żeby znać "old_value"
    old_status = None
    if change:
        old_status = ServiceOrder.objects.get(pk=obj.pk).status

    super().save_model(request, obj, form, change)

    # 1) Log: utworzenie zlecenia
    if not change:
        AuditLog.objects.create(
            order=obj,
            entity_type=AuditLog.EntityType.SERVICE_ORDER,
            entity_id=obj.id,
            action=AuditLog.Action.ORDER_CREATED,
            old_value=None,
            new_value=f"status={obj.status}",
            performed_by=request.user,
        )
        return

    # 2) Log: zmiana statusu
    if old_status != obj.status:
        AuditLog.objects.create(
            order=obj,
            entity_type=AuditLog.EntityType.SERVICE_ORDER,
            entity_id=obj.id,
            action=AuditLog.Action.STATUS_CHANGED,
            old_value=old_status,
            new_value=obj.status,
            performed_by=request.user,
        )

