from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm, AdminUserCreationForm
from django.contrib.auth.models import Group, User
from django.db.models import Max
from django.forms.models import BaseInlineFormSet
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Service,
    ServiceOptionGroup,
    ServiceOption,
)


admin.site.site_header = "Panel administracyjny serwisu komputerowego"
admin.site.site_title = "Serwis komputerowy"
admin.site.index_title = "Administracja systemem"
admin.site.has_permission = lambda request: request.user.is_active and request.user.is_superuser
admin.site.enable_nav_sidebar = False

admin.site.unregister(User)
admin.site.unregister(Group)


ADMIN_FIELD_LABELS = {
    "name": "Nazwa",
    "base_price_min": "Cena od",
    "base_price_max": "Cena do",
    "base_duration_minutes": "Czas bazowy (minuty)",
    "service": "Usługa",
    "group": "Sekcja opcji",
    "price_delta_min": "Dopłata od",
    "price_delta_max": "Dopłata do",
    "duration_delta_minutes": "Zmiana czasu (minuty)",
    "is_active": "Widoczne",
}


class StaffAccountCreationForm(AdminUserCreationForm):
    is_superuser = forms.BooleanField(label="Uprawnienia administratora", required=False)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "is_superuser")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = ""


class StaffPasswordChangeForm(AdminPasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = ""


@admin.register(User)
class StaffAccountAdmin(UserAdmin):
    add_form = StaffAccountCreationForm
    change_password_form = StaffPasswordChangeForm
    actions = None
    list_display = ("username", "first_name", "last_name", "delete_account_link")
    list_filter = ()
    filter_horizontal = ()
    readonly_fields = ("password_reset_link",)
    search_fields = ()
    ordering = ("username",)
    fieldsets = (
        ("Dane logowania", {"fields": ("username", "password_reset_link")}),
        ("Dane pracownika", {"fields": ("first_name", "last_name")}),
        ("Dostęp do systemu", {"fields": ("is_superuser",)}),
    )
    add_fieldsets = (
        (
            "Dane konta",
            {
                "classes": ("wide",),
                "fields": ("username", "first_name", "last_name", "password1", "password2"),
            },
        ),
        ("Dostęp do systemu", {"fields": ("is_superuser",)}),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        labels = {
            "is_superuser": "Uprawnienia administratora",
        }
        if db_field.name in labels:
            formfield.label = labels[db_field.name]
        return formfield

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for field in form.base_fields.values():
            field.help_text = ""
        if "is_superuser" in form.base_fields:
            form.base_fields["is_superuser"].label = "Uprawnienia administratora"
        return form

    @admin.display(description="Hasło")
    def password_reset_link(self, obj):
        if not obj or not obj.pk:
            return "-"

        url = reverse("admin:auth_user_password_change", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}">Ustaw nowe hasło</a>',
            url,
        )

    @admin.display(description="Usuń")
    def delete_account_link(self, obj):
        if getattr(self, "_current_user_id", None) == obj.pk:
            return "-"

        url = reverse("admin:auth_user_delete", args=[obj.pk])
        return format_html('<a class="service-inline-delete" href="{}">Usuń</a>', url)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.pk == request.user.pk:
            return False
        return super().has_delete_permission(request, obj)

    def changelist_view(self, request, extra_context=None):
        self._current_user_id = request.user.pk
        extra_context = {
            **(extra_context or {}),
            "title": "Konta pracowników",
        }
        return super().changelist_view(request, extra_context)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra_context = {
            **(extra_context or {}),
            "title": "Edycja konta pracownika" if object_id else "Dodaj użytkownika",
            "show_delete": False,
        }
        return super().changeform_view(request, object_id, form_url, extra_context)

    def save_model(self, request, obj, form, change):
        obj.is_active = True
        obj.is_staff = True
        super().save_model(request, obj, form, change)


class PolishAdminLabelsMixin:
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        label = ADMIN_FIELD_LABELS.get(db_field.name)
        if label:
            formfield.label = label
        return formfield


class DeleteSelectedActionForm(forms.Form):
    action = forms.ChoiceField(
        initial="delete_selected",
        required=False,
        widget=forms.HiddenInput,
    )
    select_across = forms.BooleanField(
        initial=False,
        required=False,
        widget=forms.HiddenInput,
    )


class ServiceAdminForm(forms.ModelForm):
    manual_pricing = forms.BooleanField(
        label="Cena do ustalenia po diagnozie",
        required=False,
    )

    class Meta:
        model = Service
        fields = (
            "name",
            "description",
            "is_active",
            "manual_pricing",
            "base_price_min",
            "base_price_max",
            "base_duration_minutes",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manual_pricing"].initial = self.instance.requires_manual_pricing

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("manual_pricing"):
            instance.pricing_mode = Service.PricingMode.MANUAL_AFTER_DIAGNOSIS
        else:
            instance.pricing_mode = Service.PricingMode.CONFIGURABLE

        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ServiceOptionGroupInlineForm(forms.ModelForm):
    price_delta_min = forms.DecimalField(
        label="Dopłata od",
        max_digits=10,
        decimal_places=2,
        required=False,
    )
    price_delta_max = forms.DecimalField(
        label="Dopłata do",
        max_digits=10,
        decimal_places=2,
        required=False,
    )

    class Meta:
        model = ServiceOptionGroup
        fields = ("name", "price_delta_min", "price_delta_max")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "name" in self.fields:
            self.fields["name"].label = "Nazwa opcji"

        primary_option = self.get_primary_option()
        if primary_option and not self.is_bound:
            self.initial["price_delta_min"] = primary_option.price_delta_min
            self.initial["price_delta_max"] = primary_option.price_delta_max

    def clean_price_delta_min(self):
        return self.cleaned_data.get("price_delta_min") or 0

    def clean_price_delta_max(self):
        return self.cleaned_data.get("price_delta_max") or 0

    def clean(self):
        cleaned_data = super().clean()
        price_delta_min = cleaned_data.get("price_delta_min") or 0
        price_delta_max = cleaned_data.get("price_delta_max") or 0
        if price_delta_max < price_delta_min:
            self.add_error("price_delta_max", "Dopłata do nie może być niższa niż dopłata od.")
        return cleaned_data

    def get_primary_option(self):
        if not self.instance.pk:
            return None
        return self.instance.options.order_by("sort_order", "id").first()

    def save_option(self, group):
        options = list(group.options.order_by("sort_order", "id"))
        option = options[0] if options else ServiceOption(group=group, sort_order=10)
        option.name = group.name
        option.price_delta_min = self.cleaned_data.get("price_delta_min") or 0
        option.price_delta_max = self.cleaned_data.get("price_delta_max") or 0
        option.duration_delta_minutes = 0
        option.is_active = group.is_active
        option.save()

        for extra_option in options[1:]:
            extra_option.is_active = False
            extra_option.save(update_fields=["is_active"])


class ServiceOptionGroupInlineFormSet(BaseInlineFormSet):
    def save_new(self, form, commit=True):
        obj = form.save(commit=False)
        obj.service = self.instance
        obj.selection_type = ServiceOptionGroup.SelectionType.MULTI
        obj.is_required = False
        obj.is_active = True
        if obj.sort_order == 0:
            obj.sort_order = self.get_next_sort_order()

        if commit:
            obj.save()
            form.save_m2m()
            form.save_option(obj)
        return obj

    def save_existing(self, form, instance, commit=True):
        obj = form.save(commit=False)
        obj.selection_type = ServiceOptionGroup.SelectionType.MULTI
        obj.is_required = False
        obj.is_active = True
        if commit:
            obj.save()
            form.save_m2m()
            form.save_option(obj)
        return obj

    def get_next_sort_order(self):
        max_order = ServiceOptionGroup.objects.filter(service=self.instance).aggregate(
            Max("sort_order")
        )["sort_order__max"]
        return (max_order or 0) + 10


class ServiceOptionGroupInline(PolishAdminLabelsMixin, admin.TabularInline):
    model = ServiceOptionGroup
    form = ServiceOptionGroupInlineForm
    formset = ServiceOptionGroupInlineFormSet
    extra = 1
    fields = ("name", "price_delta_min", "price_delta_max")
    can_delete = False
    verbose_name = "Opcja usługi"
    verbose_name_plural = "Opcje usługi"


@admin.register(Service)
class ServiceAdmin(PolishAdminLabelsMixin, admin.ModelAdmin):
    form = ServiceAdminForm
    action_form = DeleteSelectedActionForm
    actions = ["delete_selected"]
    change_list_template = "admin/orders/service/change_list.html"
    list_display = (
        "name",
        "price_range_display",
        "duration_display",
        "is_active",
    )
    list_filter = ()
    search_fields = ()
    inlines = [ServiceOptionGroupInline]
    fieldsets = (
        ("Podstawowe informacje", {"fields": ("name", "description", "is_active")}),
        (
            "Cena i czas",
            {"fields": ("manual_pricing", "base_price_min", "base_price_max", "base_duration_minutes")},
        ),
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

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for field in form.base_fields.values():
            field.help_text = ""
        labels = {
            "name": "Nazwa usługi",
            "description": "Opis",
            "is_active": "Widoczna dla klienta",
        }
        for field_name, label in labels.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].label = label
        for field_name in ("base_price_min", "base_price_max"):
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = "Przy stałej cenie wpisz tę samą kwotę w obu polach."
        return form

    def render_change_form(self, request, context, add=False, change=False, form_url="", obj=None):
        context["show_delete"] = False
        return super().render_change_form(request, context, add, change, form_url, obj)
