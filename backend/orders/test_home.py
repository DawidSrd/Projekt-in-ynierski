from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib import admin
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from .admin import ServiceOrderAdmin
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
        self.assertContains(response, "Najczęstsze usługi")
        self.assertContains(response, "Najczęstsze problemy")
        self.assertContains(response, "Nie pasuje żadna konkretna usługa?")
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
        self.assertNotContains(response, "Utworzenie zlecenia")
        self.assertNotContains(response, "Aktualne zgłoszenie")
        self.assertNotContains(response, "Diagnostyka laptopa")
        self.assertNotContains(response, "Dlaczego warto?")
        self.assertNotContains(response, "FAQ")
        self.assertNotContains(response, "Panel technika")
        self.assertNotContains(response, "Admin")
        self.assertNotContains(response, 'href="/tech/dashboard/"')
        self.assertNotContains(response, 'href="/admin/"')

    def test_home_page_shows_active_services_preview(self):
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
        self.assertContains(response, "Diagnostyka sprzętu")
        self.assertContains(response, "Sprawdzenie stanu komputera.")
        self.assertContains(response, "80,00 - 120,00 zł")
        self.assertContains(response, "Wybierz usługę")
        self.assertNotContains(response, "Usługa ukryta")

    def test_service_catalog_groups_services_and_uses_human_time_labels(self):
        Service.objects.create(
            name="Diagnostyka komputera lub laptopa",
            description="Gdy nie wiadomo, co powoduje problem.",
            base_price_min=80,
            base_price_max=160,
            is_active=True,
        )
        Service.objects.create(
            name="Instalacja systemu Windows",
            description="Instalacja systemu, sterowników i podstawowa konfiguracja.",
            base_price_min=140,
            base_price_max=260,
            is_active=True,
        )
        Service.objects.create(
            name="Inne / indywidualna diagnoza",
            description="Dla problemów, które nie pasują do standardowych usług.",
            base_price_min=0,
            base_price_max=0,
            pricing_mode=Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
            is_active=True,
        )

        response = self.client.get(reverse("service_catalog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Diagnostyka i naprawa")
        self.assertContains(response, "System i oprogramowanie")
        self.assertContains(response, "Ceny i terminy są orientacyjne")
        self.assertContains(response, "Orientacyjnie: 1 dzień roboczy")
        self.assertNotContains(response, "90 min")
        self.assertContains(response, "Nie pasuje żadna konkretna usługa?")
        self.assertContains(response, "Wybierz indywidualną diagnozę")

    def test_track_page_explains_guest_access_result(self):
        response = self.client.get(reverse("track_order"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Numer zlecenia znajdziesz w potwierdzeniu zgłoszenia")
        self.assertContains(response, "Co zobaczysz po sprawdzeniu?")
        self.assertContains(response, "aktualny status zlecenia")
        self.assertContains(response, "komentarze publiczne od serwisu")

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
        self.assertContains(response, "Zakres prac")
        self.assertContains(response, "Jak skorzystać z usługi")
        self.assertContains(response, "Godziny otwarcia")
        self.assertContains(response, "Kontakt")
        self.assertContains(response, "Zajmujemy się diagnozą i naprawą")
        self.assertContains(response, "sprawdzić aktualny status naprawy")
        self.assertContains(response, "500 100 200")
        self.assertNotContains(response, "Historia obsługi")
        self.assertNotContains(response, "Wycena przed rozpoczęciem prac")

    def test_admin_index_uses_custom_dashboard(self):
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
        self.assertContains(response, "Panel administratora")
        self.assertContains(response, "Administracja serwisem")
        self.assertContains(response, "Panel technika")
        self.assertContains(response, 'href="/tech/dashboard/"')
        self.assertContains(response, "Aktywne")
        self.assertContains(response, "Nieprzypisane")
        self.assertContains(response, "Czeka na klienta")
        self.assertContains(response, "Ostatnie zlecenia")
        self.assertContains(response, "Jan Kowalski")
        self.assertContains(response, "Pokaż wszystkie dane systemu")
        self.assertContains(response, "Ostatnie działania")

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

    def test_admin_status_change_logs_audit_entry_without_email_option(self):
        admin_user = User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        order = ServiceOrder.objects.create(
            customer_name="Jan Kowalski",
            customer_email="jan@example.com",
            customer_phone="123456789",
        )
        model_admin = ServiceOrderAdmin(ServiceOrder, admin.site)
        request = RequestFactory().post("/admin/")
        request.user = admin_user
        form_class = model_admin.get_form(request, order)
        self.assertNotIn("notify_customer", form_class.base_fields)

        form = form_class(
            data={
                "status": ServiceOrderStatus.RECEIVED,
                "customer_name": order.customer_name,
                "customer_email": order.customer_email,
                "customer_phone": order.customer_phone,
                "device_type": "",
                "device_brand": "",
                "device_model": "",
                "device_issue_description": "",
                "diagnosis": "",
                "repair_notes": "",
                "final_price": "",
                "customer_accepted_repair": "",
                "assigned_technician": "",
                "estimated_completion_at_0": "",
                "estimated_completion_at_1": "",
            },
            instance=order,
        )
        self.assertTrue(form.is_valid())
        model_admin.save_model(request, form.instance, form, True)
        self.assertTrue(
            AuditLog.objects.filter(
                order=order,
                action=AuditLog.Action.STATUS_CHANGED,
                old_value=ServiceOrderStatus.NEW,
                new_value=ServiceOrderStatus.RECEIVED,
                performed_by=admin_user,
            ).exists()
        )

    def test_admin_order_page_uses_secure_attachment_link(self):
        User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        order = ServiceOrder.objects.create(
            customer_name="Jan Kowalski",
            customer_email="jan@example.com",
            customer_phone="123456789",
        )
        attachment = ServiceOrderAttachment.objects.create(
            order=order,
            visibility=ServiceOrderAttachment.Visibility.PUBLIC,
            file=SimpleUploadedFile(
                "diagnoza.pdf",
                b"test-pdf-content",
                content_type="application/pdf",
            ),
            original_name="diagnoza.pdf",
        )
        self.client.login(username="admin", password="testpass123")

        response = self.client.get(reverse("admin:orders_serviceorder_change", args=[order.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("attachment_download", args=[attachment.id]))
        self.assertNotContains(response, attachment.file.url)
