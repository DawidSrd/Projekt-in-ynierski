from django import forms
from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from .choices import get_available_order_status_choices
from .audit import (
    format_service_result,
    log_comment_added,
    log_diagnosis_updated,
    log_estimate_set,
    log_order_created,
    log_status_changed,
    log_technician_assigned,
)
from .emails import build_status_change_email, send_customer_email
from .models import (
    Service,
    ServiceOptionGroup,
    ServiceOption,
    ServiceOrder,
    ServiceOrderAttachment,
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
        "pricing_mode",
        "price_range_display",
        "duration_display",
        "is_active",
        "option_groups_count",
    )
    list_filter = ("pricing_mode", "is_active")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [ServiceOptionGroupInline]
    fieldsets = (
        ("Dane usługi", {"fields": ("name", "description", "pricing_mode", "is_active")}),
        (
            "Wycena i czas realizacji",
            {"fields": ("base_price_min", "base_price_max", "base_duration_minutes")},
        ),
        ("Metadane", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Przedział cenowy")
    def price_range_display(self, obj):
        if obj.requires_manual_pricing:
            return "Wycena po diagnozie"
        return f"{obj.base_price_min} - {obj.base_price_max} zł"

    @admin.display(description="Czas bazowy")
    def duration_display(self, obj):
        if obj.requires_manual_pricing:
            return "Po diagnozie"
        return f"{obj.base_duration_minutes} min"

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


class ServiceOrderAttachmentInline(admin.TabularInline):
    model = ServiceOrderAttachment
    extra = 0
    fields = ("visibility", "download_link", "original_name", "uploaded_by", "created_at")
    readonly_fields = ("download_link", "original_name", "uploaded_by", "created_at")
    can_delete = False

    @admin.display(description="Plik")
    def download_link(self, obj):
        if not obj.pk:
            return "-"

        return format_html(
            '<a href="{}">Pobierz</a>',
            reverse("attachment_download", args=[obj.pk]),
        )

    def has_add_permission(self, request, obj=None):
        return False


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
        "pricing_mode_snapshot",
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
            log_comment_added(obj, request.user)


@admin.register(ServiceOrderAttachment)
class ServiceOrderAttachmentAdmin(admin.ModelAdmin):
    list_display = ("order", "original_name", "download_link", "visibility", "uploaded_by", "created_at")
    list_filter = ("visibility", "created_at")
    search_fields = ("original_name", "order__order_number", "uploaded_by__username")
    fields = ("order", "visibility", "download_link", "original_name", "uploaded_by", "created_at")
    readonly_fields = ("download_link", "original_name", "uploaded_by", "created_at")
    list_select_related = ("order", "uploaded_by")

    @admin.display(description="Plik")
    def download_link(self, obj):
        return format_html(
            '<a href="{}">Pobierz</a>',
            reverse("attachment_download", args=[obj.pk]),
        )

    def has_add_permission(self, request):
        return False


class ServiceOrderAdminForm(forms.ModelForm):
    notify_customer = forms.BooleanField(
        required=False,
        label="Wyślij klientowi wiadomość e-mail o zmianie statusu",
    )

    class Meta:
        model = ServiceOrder
        fields = "__all__"


@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    form = ServiceOrderAdminForm
    list_display = (
        "order_number",
        "customer_name",
        "device_display",
        "assigned_technician",
        "status",
        "final_price",
        "customer_accepted_repair",
        "estimated_completion_at",
        "overdue_display",
        "items_count",
        "created_at",
    )
    list_filter = (
        "status",
        "device_type",
        "assigned_technician",
        "customer_accepted_repair",
        OverdueFilter,
        "created_at",
    )
    search_fields = (
        "order_number",
        "customer_name",
        "customer_email",
        "customer_phone",
        "device_brand",
        "device_model",
        "device_issue_description",
        "diagnosis",
        "repair_notes",
        "assigned_technician__username",
    )
    readonly_fields = ("order_number", "created_at", "updated_at", "overdue_display")
    inlines = [ServiceOrderItemInline, ServiceOrderCommentInline, ServiceOrderAttachmentInline, AuditLogInline]
    date_hierarchy = "created_at"
    fieldsets = (
        ("Identyfikacja", {"fields": ("order_number", "status")}),
        ("Dane klienta", {"fields": ("customer_name", "customer_email", "customer_phone")}),
        (
            "Urządzenie",
            {"fields": ("device_type", "device_brand", "device_model", "device_issue_description")},
        ),
        (
            "Diagnoza i rozliczenie",
            {"fields": ("diagnosis", "repair_notes", "final_price", "customer_accepted_repair")},
        ),
        (
            "Obsługa serwisowa",
            {
                "fields": (
                    "assigned_technician",
                    "estimated_completion_at",
                    "notify_customer",
                    "overdue_display",
                )
            },
        ),
        ("Metadane", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(boolean=True, description="Przeterminowane")
    def overdue_display(self, obj):
        return obj.is_overdue()

    @admin.display(description="Pozycje")
    def items_count(self, obj):
        return obj.items.count()

    @admin.display(description="Urządzenie")
    def device_display(self, obj):
        parts = [
            obj.get_device_type_display() if obj.device_type else "",
            obj.device_brand,
            obj.device_model,
        ]
        return " ".join(part for part in parts if part) or "brak"

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
        old_service_result = None
        old_assigned_technician = None

        if change:
            old_obj = ServiceOrder.objects.get(pk=obj.pk)
            old_status = old_obj.status
            old_estimate = old_obj.estimated_completion_at
            old_assigned_technician = old_obj.assigned_technician
            old_service_result = format_service_result(old_obj)

        super().save_model(request, obj, form, change)

        # Log: utworzenie zlecenia (admin)
        if not change:
            log_order_created(obj, request.user)
            return

        notify_customer = form.cleaned_data.get("notify_customer", False)

        # Log + mail: zmiana statusu
        if old_status != obj.status:
            log_status_changed(obj, old_status, request.user)

            if notify_customer:
                subject, message = build_status_change_email(obj)
                email_sent = send_customer_email(subject, message, obj.customer_email)
                if not email_sent:
                    self.message_user(
                        request,
                        "Status został zapisany, ale nie udało się wysłać wiadomości e-mail do klienta.",
                        level=messages.WARNING,
                    )

        # Log: zmiana estymacji
        if old_estimate != obj.estimated_completion_at:
            log_estimate_set(obj, old_estimate, request.user)

        if old_assigned_technician != obj.assigned_technician:
            log_technician_assigned(
                obj,
                old_technician=old_assigned_technician,
                new_technician=obj.assigned_technician,
                performed_by=request.user,
            )

        if old_service_result != format_service_result(obj):
            log_diagnosis_updated(obj, old_service_result, request.user)



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
        "pricing_mode_snapshot",
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
        if obj.requires_manual_pricing:
            return "Wycena po diagnozie"
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
