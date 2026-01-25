from django.contrib import admin
from .models import Service, ServiceOptionGroup, ServiceOption, ServiceOrder
from .models import ServiceOrderComment


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


@admin.register(ServiceOrder)
class ServiceOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer_name", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("order_number", "customer_name", "customer_email", "customer_phone")
    inlines = [ServiceOrderCommentInline]
