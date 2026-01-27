from django.contrib import admin
from django.core.mail import send_mail

from .models import (
    Service,
    ServiceOptionGroup,
    ServiceOption,
    ServiceOrder,
    ServiceOrderComment,
    AuditLog,
)

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "base_price_min",
        "base_price_max",
        "base_duration_minutes",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(ServiceOptionGroup)
class ServiceOptionGroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "service",
        "selection_type",
        "is_required",
        "is_active",
        "sort_order",
    )
    list_filter = ("selection_type", "is_required", "is_active")
    search_fields = ("name", "service__name")


@admin.register(ServiceOption)
class ServiceOptionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "group",
        "price_delta_min",
        "price_delta_max",
        "duration_delta_minutes",
        "is_active",
        "sort_order",
    )
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


class OverdueFilter(admin.SimpleListFilter):
    title = "Przeterminowane"
    parameter_name = "overdue"

    def lookups(self, request, model_admin):
        return (("yes", "Tak"), ("no", "Nie"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return [o for o in queryset if o.is_overdue()]
        if self.value() == "no":
            return [o for o in queryset if not o.is_overdue()]
        return queryset


@admin.register(ServiceOrderComment)
class ServiceOrderCommentAdmin(admin.ModelAdmin):
    list_display = ("order", "visibility", "created_at")
    list_filter = ("visibility",)
    search_fields = ("content", "order__order_number")
    readonly_fields = ("created_at",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Logujemy tylko nowe komentarze (nie edycję)
        if not change:
            AuditLog.objects.create(
                order=obj.order,
                entity_type=AuditLog.EntityType.SERVICE_ORDER_COMMENT,
                entity_id=obj.id,
                action=AuditLog.Action.COMMENT_ADDED,
                new_value=f"visibility={obj.visibility}",
                performed_by=request.user,
            )


@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "customer_name",
        "status",
        "estimated_completion_at",
        "overdue_display",
        "created_at",
    )
    list_filter = ("status", OverdueFilter)
    search_fields = ("order_number", "customer_name", "customer_email", "customer_phone")
    inlines = [ServiceOrderCommentInline, AuditLogInline]

    @admin.display(boolean=True, description="Przeterminowane")
    def overdue_display(self, obj):
        return obj.is_overdue()

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

        # Log: utworzenie zlecenia (admin)
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

        # Log + mail: zmiana statusu
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

            send_mail(
                subject=f"Zmiana statusu zlecenia {obj.order_number}",
                message=(
                    f"Status Twojego zlecenia {obj.order_number} został zmieniony.\n\n"
                    f"Aktualny status: {obj.get_status_display()}\n"
                ),
                from_email=None,
                recipient_list=[obj.customer_email],
            )

        # Log: zmiana estymacji
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
    readonly_fields = (
        "entity_type",
        "entity_id",
        "action",
        "old_value",
        "new_value",
        "performed_by",
        "performed_at",
        "order",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
