from django.contrib import admin
from django.core.mail import send_mail

from .choices import get_available_order_status_choices
from .models import (
    Service,
    ServiceOptionGroup,
    ServiceOption,
    ServiceOrder,
    ServiceOrderComment,
    ServiceOrderItem,
    ServiceOrderItemOption,
    AuditLog,
)


admin.site.site_header = "Panel administracyjny serwisu komputerowego"
admin.site.site_title = "Serwis komputerowy"
admin.site.index_title = "Zarządzanie systemem obsługi zleceń"
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser


class ServiceOptionGroupInline(admin.TabularInline):
    model = ServiceOptionGroup
    extra = 0
    fields = ("name", "selection_type", "is_required", "is_active", "sort_order")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price_range_display",
        "base_duration_minutes",
        "is_active",
        "option_groups_count",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [ServiceOptionGroupInline]
    fieldsets = (
        ("Dane usługi", {"fields": ("name", "description", "is_active")}),
        (
            "Wycena i czas realizacji",
            {"fields": ("base_price_min", "base_price_max", "base_duration_minutes")},
        ),
        ("Metadane", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Przedział cenowy")
    def price_range_display(self, obj):
        return f"{obj.base_price_min} - {obj.base_price_max} zł"

    @admin.display(description="Grupy opcji")
    def option_groups_count(self, obj):
        return obj.option_groups.count()


class ServiceOptionInline(admin.TabularInline):
    model = ServiceOption
    extra = 0
    fields = (
        "name",
        "price_delta_min",
        "price_delta_max",
        "duration_delta_minutes",
        "is_active",
        "sort_order",
    )


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
    list_select_related = ("service",)
    inlines = [ServiceOptionInline]
    fieldsets = (
        ("Powiązanie", {"fields": ("service",)}),
        ("Konfiguracja grupy", {"fields": ("name", "selection_type", "is_required")}),
        ("Widoczność i kolejność", {"fields": ("is_active", "sort_order")}),
    )


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
    list_filter = ("is_active", "group__service")
    search_fields = ("name", "group__name", "group__service__name")
    list_select_related = ("group", "group__service")
    fieldsets = (
        ("Powiązanie", {"fields": ("group",)}),
        ("Dane opcji", {"fields": ("name", "is_active", "sort_order")}),
        (
            "Wpływ na wycenę i czas",
            {"fields": ("price_delta_min", "price_delta_max", "duration_delta_minutes")},
        ),
    )


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


class ServiceOrderItemInline(admin.TabularInline):
    model = ServiceOrderItem
    extra = 0
    fields = (
        "service_name_snapshot",
        "base_price_min_snapshot",
        "base_price_max_snapshot",
        "calculated_price_min",
        "calculated_price_max",
        "created_at",
    )
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class OverdueFilter(admin.SimpleListFilter):
    title = "Przeterminowane"
    parameter_name = "overdue"

    def lookups(self, request, model_admin):
        return (("yes", "Tak"), ("no", "Nie"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            overdue_ids = [o.id for o in queryset if o.is_overdue()]
            return queryset.filter(id__in=overdue_ids)
        if self.value() == "no":
            overdue_ids = [o.id for o in queryset if o.is_overdue()]
            return queryset.exclude(id__in=overdue_ids)
        return queryset


@admin.register(ServiceOrderComment)
class ServiceOrderCommentAdmin(admin.ModelAdmin):
    list_display = ("order", "visibility", "content_preview", "created_at")
    list_filter = ("visibility",)
    search_fields = ("content", "order__order_number")
    readonly_fields = ("created_at",)
    list_select_related = ("order",)

    @admin.display(description="Treść")
    def content_preview(self, obj):
        return obj.content[:80]

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
        "items_count",
        "created_at",
    )
    list_filter = ("status", OverdueFilter, "created_at")
    search_fields = ("order_number", "customer_name", "customer_email", "customer_phone")
    readonly_fields = ("order_number", "created_at", "updated_at", "overdue_display")
    inlines = [ServiceOrderItemInline, ServiceOrderCommentInline, AuditLogInline]
    date_hierarchy = "created_at"
    fieldsets = (
        ("Identyfikacja", {"fields": ("order_number", "status")}),
        ("Dane klienta", {"fields": ("customer_name", "customer_email", "customer_phone")}),
        ("Obsługa serwisowa", {"fields": ("estimated_completion_at", "overdue_display")}),
        ("Metadane", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(boolean=True, description="Przeterminowane")
    def overdue_display(self, obj):
        return obj.is_overdue()

    @admin.display(description="Pozycje")
    def items_count(self, obj):
        return obj.items.count()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        if obj and "status" in form.base_fields:
            form.base_fields["status"].choices = get_available_order_status_choices(obj.status)

        return form

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



class ServiceOrderItemOptionInline(admin.TabularInline):
    model = ServiceOrderItemOption
    extra = 0
    fields = (
        "option_name_snapshot",
        "price_delta_min_snapshot",
        "price_delta_max_snapshot",
    )
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ServiceOrderItem)
class ServiceOrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "service_name_snapshot",
        "calculated_price_display",
        "created_at",
    )
    list_filter = ("service", "created_at")
    search_fields = ("order__order_number", "service_name_snapshot")
    readonly_fields = (
        "order",
        "service",
        "service_name_snapshot",
        "base_price_min_snapshot",
        "base_price_max_snapshot",
        "calculated_price_min",
        "calculated_price_max",
        "created_at",
    )
    inlines = [ServiceOrderItemOptionInline]
    list_select_related = ("order", "service")

    @admin.display(description="Wycena końcowa")
    def calculated_price_display(self, obj):
        return f"{obj.calculated_price_min} - {obj.calculated_price_max} zł"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ServiceOrderItemOption)
class ServiceOrderItemOptionAdmin(admin.ModelAdmin):
    list_display = (
        "order_item",
        "option_name_snapshot",
        "price_delta_min_snapshot",
        "price_delta_max_snapshot",
    )
    search_fields = (
        "order_item__order__order_number",
        "option_name_snapshot",
    )
    readonly_fields = (
        "order_item",
        "option",
        "option_name_snapshot",
        "price_delta_min_snapshot",
        "price_delta_max_snapshot",
    )
    list_select_related = ("order_item", "order_item__order", "option")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("entity_type", "entity_id", "action", "order", "performed_by", "performed_at")
    list_filter = ("entity_type", "action", "performed_at")
    search_fields = ("entity_type", "entity_id", "old_value", "new_value", "performed_by__username")
    list_select_related = ("order", "performed_by")
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
