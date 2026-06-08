from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.contrib import admin
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from .admin import ServiceOptionGroupInlineForm, StaffAccountAdmin, ServiceAdmin
from .choices import ServiceOrderStatus
from .models import (
    AuditLog,
    Service,
    ServiceOption,
    ServiceOptionGroup,
    ServiceOrder,
    ServiceOrderAttachment,
    ServiceOrderComment,
    ServiceOrderItem,
    ServiceOrderItemOption,
)

class HomePageTests(TestCase):
    def test_anonymous_home_page_shows_client_entry_points(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Naprawa laptopów i komputerów")
        self.assertContains(response, "Utwórz zgłoszenie przed wizytą")
        self.assertContains(response, "Przyjęcie sprzętu")
        self.assertContains(response, "na miejscu przy odbiorze")
        self.assertContains(response, "Czym się zajmujemy")
        self.assertContains(response, "Nie widzisz swojego problemu na liście?")
        self.assertContains(response, "Przejdź do katalogu")
        self.assertContains(response, "Telefon: 500 100 200")
        self.assertContains(response, "Jak wygląda obsługa")
        self.assertContains(response, "Zgłaszasz problem")
        self.assertContains(response, "Odbierasz sprzęt")
        self.assertContains(response, "Co zobaczysz w zleceniu?")
        self.assertContains(response, "Planowany termin")
        self.assertContains(response, "Śledź zlecenie")
        self.assertContains(response, "Zgłoś naprawę")
        self.assertContains(response, "O nas")
        self.assertContains(response, "500 100 200")
        self.assertContains(response, 'href="/about/"')
        self.assertContains(response, 'href="/services/"')
        self.assertContains(response, 'href="/track/"')
        self.assertContains(response, 'href="/staff/login/"')
        self.assertContains(response, ">Usługi<")
        self.assertContains(response, "System obsługi zleceń serwisowych")
        self.assertContains(response, "2026")
        self.assertNotContains(response, "Panel technika")
        self.assertNotContains(response, "Admin")
        self.assertNotContains(response, 'href="/tech/dashboard/"')
        self.assertNotContains(response, 'href="/admin/"')

    def test_home_page_does_not_render_catalog_entries(self):
        Service.objects.create(
            name="Diagnostyka sprzętu",
            description="Sprawdzenie stanu komputera.",
            base_price_min=80,
            base_price_max=120,
            is_active=True,
        )
        Service.objects.create(
            name="Usługa ukryta",
            base_price_min=50,
            base_price_max=70,
            is_active=False,
        )

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "diagnostyka laptopów i komputerów")
        self.assertContains(response, "indywidualna diagnoza problemów")
        self.assertContains(response, 'href="/services/"')
        self.assertNotContains(response, "Diagnostyka sprzętu")
        self.assertNotContains(response, "Sprawdzenie stanu komputera.")
        self.assertNotContains(response, "80,00 - 120,00 zł")
        self.assertNotContains(response, "Wybierz usługę")
        self.assertNotContains(response, "Usługa ukryta")

    def test_service_catalog_shows_active_services_and_configured_duration(self):
        Service.objects.create(
            name="Diagnostyka komputera lub laptopa",
            description="Gdy nie wiadomo, co powoduje problem.",
            base_price_min=80,
            base_price_max=160,
            base_duration_minutes=90,
            catalog_position=2,
            is_active=True,
        )
        first_service = Service.objects.create(
            name="Instalacja systemu Windows",
            description="Instalacja systemu, sterowników i podstawowa konfiguracja.",
            base_price_min=140,
            base_price_max=260,
            catalog_position=1,
            is_active=True,
        )
        Service.objects.create(
            name="Inne / indywidualna diagnoza",
            description="Dla problemów, które nie pasują do standardowych usług.",
            base_price_min=0,
            base_price_max=0,
            pricing_mode=Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
            is_featured=True,
            is_active=True,
        )
        Service.objects.create(
            name="Testowa usługa administratora",
            description="Usługa dodana bez zmiany kodu.",
            base_price_min=50,
            base_price_max=100,
            base_duration_minutes=120,
            pricing_mode=Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
            is_active=True,
        )

        response = self.client.get(reverse("service_catalog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Diagnostyka komputera lub laptopa")
        self.assertContains(response, "Instalacja systemu Windows")
        self.assertContains(response, "Testowa usługa administratora")
        self.assertContains(response, "Usługa dodana bez zmiany kodu.")
        self.assertContains(response, "Ceny i terminy są orientacyjne")
        self.assertContains(response, "90 min")
        self.assertContains(response, "120 min")
        self.assertEqual(response.context["services"].first(), first_service)
        self.assertEqual(
            response.context["featured_service"].name,
            "Inne / indywidualna diagnoza",
        )
        self.assertContains(response, "Nie pasuje żadna konkretna usługa?")
        self.assertContains(response, "Wybierz indywidualną diagnozę")

    def test_track_page_explains_guest_access_result(self):
        response = self.client.get(reverse("track_order"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Numer zlecenia znajdziesz w potwierdzeniu zgłoszenia")
        self.assertContains(response, "Co zobaczysz po sprawdzeniu?")
        self.assertContains(response, "aktualny status zlecenia")
        self.assertContains(response, "komentarze od serwisu")

    def test_staff_user_sees_technician_navigation_only(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.get(reverse("tech_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel technika")
        self.assertContains(response, 'href="/tech/dashboard/"')
        self.assertContains(response, 'action="/staff/logout/"')
        self.assertNotContains(response, 'href="/"')
        self.assertNotContains(response, 'href="/about/"')
        self.assertNotContains(response, 'href="/services/"')
        self.assertNotContains(response, 'href="/track/"')
        self.assertNotContains(response, ">Start<")
        self.assertNotContains(response, ">Usługi<")
        self.assertNotContains(response, ">Śledzenie<")
        self.assertNotContains(response, "Admin")
        self.assertNotContains(response, 'href="/admin/"')

    def test_superuser_sees_technician_and_admin_navigation(self):
        User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        self.client.login(username="admin", password="testpass123")

        response = self.client.get(reverse("tech_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel technika")
        self.assertContains(response, "Admin")
        self.assertContains(response, 'href="/tech/dashboard/"')
        self.assertContains(response, 'href="/admin/"')
        self.assertNotContains(response, 'href="/about/"')
        self.assertNotContains(response, 'href="/services/"')
        self.assertNotContains(response, 'href="/track/"')

    def test_staff_user_is_redirected_from_client_area(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=100,
            base_price_max=150,
        )

        client_urls = [
            reverse("home"),
            reverse("about"),
            reverse("service_catalog"),
            reverse("service_configurator", args=[service.id]),
            reverse("track_order"),
            reverse("order_created", args=["SRV-ABC12345"]),
        ]

        for url in client_urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], reverse("tech_dashboard"))

    def test_about_page_has_service_information(self):
        response = self.client.get(reverse("about"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "O nas")
        self.assertContains(response, "Czym się zajmujemy")
        self.assertContains(response, "Zakres obsługi")
        self.assertContains(response, "Jak skorzystać z usługi")
        self.assertContains(response, "Godziny otwarcia")
        self.assertContains(response, "Kontakt")
        self.assertContains(response, "Zajmujemy się diagnozą i naprawą")
        self.assertContains(response, "sprawdzić aktualny status naprawy")
        self.assertContains(response, "Nie musisz zakładać konta")
        self.assertContains(response, "indywidualna diagnoza problemów")
        self.assertContains(response, "500 100 200")
    def test_admin_index_focuses_on_system_administration(self):
        User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        ServiceOrder.objects.create(
            customer_name="Jan Kowalski",
            customer_email="jan@example.com",
            customer_phone="123456789",
            diagnosis="Uszkodzony dysk SSD.",
            final_price=350,
        )
        ServiceOrder.objects.create(
            customer_name="Anna Nowak",
            customer_email="anna@example.com",
            customer_phone="111222333",
            status=ServiceOrderStatus.COMPLETED,
        )
        self.client.login(username="admin", password="testpass123")

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Administracja systemem")
        self.assertContains(response, "Konta pracowników")
        self.assertContains(response, "Dodaj konto")
        self.assertContains(response, "Usługi i cennik")
        self.assertContains(response, "Panel technika")
        self.assertContains(response, 'href="/tech/dashboard/"')
        self.assertContains(response, "Usługi")
        self.assertNotContains(response, 'href="/admin/orders/serviceoptiongroup/"')
        self.assertNotContains(response, 'href="/admin/orders/serviceoption/"')
        self.assertNotContains(response, "Jan Kowalski")
        self.assertFalse(admin.site.is_registered(ServiceOrder))
        self.assertFalse(admin.site.is_registered(ServiceOrderComment))
        self.assertFalse(admin.site.is_registered(ServiceOrderAttachment))
        self.assertFalse(admin.site.is_registered(ServiceOrderItem))
        self.assertFalse(admin.site.is_registered(ServiceOrderItemOption))
        self.assertFalse(admin.site.is_registered(AuditLog))
        self.assertFalse(admin.site.is_registered(ServiceOptionGroup))
        self.assertFalse(admin.site.is_registered(ServiceOption))
        self.assertFalse(admin.site.is_registered(Group))

    def test_admin_lists_do_not_show_filter_sidebar(self):
        User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        self.client.login(username="admin", password="testpass123")

        urls = [
            reverse("admin:auth_user_changelist"),
            reverse("admin:orders_service_changelist"),
        ]

        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'id="changelist-filter"')
            self.assertNotContains(response, "Filtruj")

    def test_user_admin_is_simple_for_employee_accounts(self):
        admin_user = User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        technician = User.objects.create_user(
            username="technik",
            password="testpass123",
            email="technik@example.com",
            is_staff=True,
        )
        self.client.login(username="admin", password="testpass123")

        user_admin = admin.site._registry[User]
        self.assertIsInstance(user_admin, StaffAccountAdmin)
        self.assertEqual(user_admin.list_filter, ())
        self.assertEqual(user_admin.filter_horizontal, ())
        self.assertEqual(user_admin.search_fields, ())
        self.assertIsNone(user_admin.actions)
        self.assertNotIn("email", user_admin.list_display)
        self.assertNotIn("is_active", user_admin.list_display)
        self.assertNotIn("is_staff", user_admin.list_display)
        self.assertIn("delete_account_link", user_admin.list_display)
        self.assertNotIn("email", user_admin.fieldsets[1][1]["fields"])
        self.assertNotIn("email", user_admin.add_fieldsets[0][1]["fields"])
        self.assertNotIn("password", user_admin.fieldsets[0][1]["fields"])
        self.assertIn("password_reset_link", user_admin.fieldsets[0][1]["fields"])
        self.assertNotIn("is_active", user_admin.fieldsets[2][1]["fields"])
        self.assertNotIn("is_staff", user_admin.fieldsets[2][1]["fields"])

        response = self.client.get(reverse("admin:auth_user_change", args=[technician.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edycja konta pracownika")
        self.assertContains(response, "Dane pracownika")
        self.assertContains(response, "Dostęp do systemu")
        self.assertContains(response, "Uprawnienia administratora")
        self.assertContains(response, "Ustaw nowe hasło")
        self.assertContains(response, reverse("admin:auth_user_password_change", args=[technician.id]))
        self.assertNotContains(response, "Konto aktywne")
        self.assertNotContains(response, 'class="deletelink"')
        self.assertNotContains(response, "Adres e-mail")
        self.assertNotContains(response, 'name="email"')
        self.assertNotContains(response, "pbkdf2_sha256")

        password_response = self.client.get(reverse("admin:auth_user_password_change", args=[technician.id]))
        self.assertEqual(password_response.status_code, 200)

        changelist_response = self.client.get(reverse("admin:auth_user_changelist"))
        self.assertContains(changelist_response, "Konta pracowników")
        self.assertContains(changelist_response, "Dodaj użytkownika")
        self.assertContains(changelist_response, "Usuń")
        self.assertContains(changelist_response, reverse("admin:auth_user_delete", args=[technician.id]))
        self.assertNotContains(changelist_response, reverse("admin:auth_user_delete", args=[admin_user.id]))
        self.assertNotContains(changelist_response, "<label>Akcja:")
        self.assertNotContains(changelist_response, 'name="action"')
        self.assertNotContains(changelist_response, "Konto aktywne")

        add_response = self.client.post(
            reverse("admin:auth_user_add"),
            {
                "username": "nowy_admin",
                "first_name": "Nowy",
                "last_name": "Administrator",
                "password1": "testpass123",
                "password2": "testpass123",
                "is_superuser": "on",
                "_save": "Zapisz",
            },
        )

        self.assertEqual(add_response.status_code, 302)
        new_admin = User.objects.get(username="nowy_admin")
        self.assertTrue(new_admin.is_staff)
        self.assertTrue(new_admin.is_active)
        self.assertTrue(new_admin.is_superuser)
        self.assertEqual(new_admin.email, "")

        self_delete_response = self.client.get(reverse("admin:auth_user_delete", args=[admin_user.id]))
        self.assertEqual(self_delete_response.status_code, 403)

    def test_service_admin_keeps_offer_editing_simple(self):
        admin_user = User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        request = RequestFactory().get("/admin/")
        request.user = admin_user

        service_admin = ServiceAdmin(Service, admin.site)
        service_form = service_admin.get_form(request)
        self.assertEqual(len(service_admin.inlines), 1)
        self.assertEqual(service_admin.inlines[0].model, ServiceOptionGroup)
        self.assertEqual(service_admin.inlines[0].fields, ("name", "price_delta_min", "price_delta_max"))
        self.assertFalse(service_admin.inlines[0].can_delete)
        self.assertEqual(service_admin.list_filter, ())
        self.assertEqual(service_admin.search_fields, ())
        self.assertNotIn("sort_order", service_form.base_fields)
        self.assertNotIn("pricing_mode", service_form.base_fields)
        self.assertIn("manual_pricing", service_form.base_fields)
        self.assertIn("is_featured", service_form.base_fields)
        self.assertEqual(service_form.base_fields["name"].label, "Nazwa usługi")
        self.assertEqual(service_form.base_fields["description"].label, "Opis")
        self.assertEqual(service_form.base_fields["catalog_position"].label, "Pozycja w katalogu")
        self.assertEqual(service_form.base_fields["manual_pricing"].label, "Cena do ustalenia po diagnozie")
        self.assertEqual(
            service_form.base_fields["is_featured"].label,
            "Wyróżnij nad katalogiem",
        )
        self.assertEqual(service_admin.readonly_fields, ())
        self.assertNotIn(
            ("Metadane", {"fields": ("created_at", "updated_at")}),
            service_admin.fieldsets,
        )

        service = Service.objects.create(
            name="Diagnostyka",
            base_price_min=80,
            base_price_max=160,
        )
        self.client.login(username="admin", password="testpass123")
        changelist_response = self.client.get(reverse("admin:orders_service_changelist"))
        self.assertContains(changelist_response, "Dodaj usługę")
        self.assertContains(changelist_response, "Usuń zaznaczone")
        self.assertNotContains(changelist_response, "Dodaj usługa")
        self.assertNotContains(changelist_response, "<label>Akcja:")

        change_response = self.client.get(reverse("admin:orders_service_change", args=[service.id]))
        self.assertEqual(change_response.status_code, 200)
        self.assertContains(change_response, "Opcje usługi")
        self.assertContains(change_response, "Dopłata od")
        self.assertContains(change_response, "Dopłata do")
        self.assertContains(change_response, "Przy stałej cenie wpisz tę samą kwotę w obu polach.")
        self.assertNotContains(change_response, 'name="option_groups-0-is_active"')
        self.assertNotContains(change_response, 'name="option_groups-0-DELETE"')
        self.assertNotContains(change_response, 'class="deletelink"')

    def test_service_admin_manual_pricing_checkbox_sets_pricing_mode(self):
        admin_user = User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        request = RequestFactory().post("/admin/")
        request.user = admin_user
        service_admin = ServiceAdmin(Service, admin.site)
        form_class = service_admin.get_form(request)

        form = form_class(
            data={
                "name": "Indywidualna diagnoza",
                "description": "Opis problemu ustalany po przyjęciu sprzętu.",
                "is_active": "on",
                "is_featured": "on",
                "manual_pricing": "on",
                "base_price_min": "0",
                "base_price_max": "0",
                "base_duration_minutes": "60",
                "catalog_position": "1",
            }
        )

        self.assertTrue(form.is_valid())
        service = form.save(commit=False)
        self.assertEqual(service.pricing_mode, Service.PricingMode.MANUAL_AFTER_DIAGNOSIS)

        invalid_price_form = form_class(
            data={**form.data, "base_price_min": "500", "base_price_max": "100"}
        )
        self.assertFalse(invalid_price_form.is_valid())
        self.assertIn("base_price_max", invalid_price_form.errors)

        service.save()
        duplicate_form = form_class(data={**form.data, "name": "Druga diagnoza"})
        self.assertFalse(duplicate_form.is_valid())
        self.assertIn("is_featured", duplicate_form.errors)

    def test_service_option_prices_are_saved_from_service_admin(self):
        admin_user = User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        request = RequestFactory().post("/admin/")
        request.user = admin_user
        service = Service.objects.create(
            name="Diagnostyka",
            base_price_min=80,
            base_price_max=160,
        )
        ServiceOptionGroup.objects.create(
            service=service,
            name="Zakres",
            sort_order=10,
        )

        service_admin = ServiceAdmin(Service, admin.site)
        inline = service_admin.inlines[0](Service, admin.site)
        formset_class = inline.get_formset(request, service)
        prefix = formset_class.get_default_prefix()
        formset = formset_class(
            data={
                f"{prefix}-TOTAL_FORMS": "1",
                f"{prefix}-INITIAL_FORMS": "0",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "1000",
                f"{prefix}-0-name": "Tryb pilny",
                f"{prefix}-0-price_delta_min": "50",
                f"{prefix}-0-price_delta_max": "100",
            },
            instance=service,
            prefix=prefix,
        )

        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()

        new_group = ServiceOptionGroup.objects.get(service=service, name="Tryb pilny")
        self.assertEqual(new_group.sort_order, 20)
        self.assertEqual(new_group.selection_type, ServiceOptionGroup.SelectionType.MULTI)
        self.assertFalse(new_group.is_required)
        self.assertTrue(new_group.is_active)
        self.assertEqual(
            list(new_group.options.values_list("name", "price_delta_min", "price_delta_max", "sort_order", "is_active")),
            [
                ("Tryb pilny", Decimal("50.00"), Decimal("100.00"), 10, True),
            ],
        )

        ServiceOption.objects.create(group=new_group, name="Drugi wariant")
        form = ServiceOptionGroupInlineForm(instance=new_group)
        self.assertFalse(form.syncs_simple_option)
        form.save_option(new_group)
        self.assertEqual(new_group.options.filter(is_active=True).count(), 2)

    def test_staff_login_page_is_available(self):
        response = self.client.get(reverse("staff_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Logowanie pracownika")
        self.assertContains(response, "Dostęp do tej części systemu")

    def test_staff_user_can_login_to_technician_panel(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )

        response = self.client.post(
            reverse("staff_login"),
            {
                "username": "technik",
                "password": "testpass123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/tech/dashboard/")

    def test_non_staff_user_cannot_login_to_staff_panel(self):
        User.objects.create_user(
            username="klient",
            password="testpass123",
            is_staff=False,
        )

        response = self.client.post(
            reverse("staff_login"),
            {
                "username": "klient",
                "password": "testpass123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "To konto nie ma dostępu do panelu pracownika.")

    def test_staff_logout_logs_user_out(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.post(reverse("staff_logout"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("home"))

        home_response = self.client.get(reverse("home"))
        self.assertNotContains(home_response, "Panel technika")
        self.assertContains(home_response, 'href="/staff/login/"')

    def test_staff_user_cannot_open_admin_index(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])
