from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib import admin
from django.test import TestCase, override_settings
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

class ServiceConfiguratorTests(TestCase):
    def test_order_created_page_links_to_prefilled_tracking(self):
        response = self.client.get(reverse("order_created", args=["SRV-ABC12345"]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dziękujemy za zgłoszenie")
        self.assertContains(response, "SRV-ABC12345")
        self.assertContains(response, 'href="/track/?order_number=SRV-ABC12345"')

    def test_tracking_form_can_be_prefilled_with_order_number(self):
        response = self.client.get(reverse("track_order"), {"order_number": "srv-abc12345"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="SRV-ABC12345"')

    def test_required_option_group_blocks_price_calculation(self):
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=100,
            base_price_max=150,
        )
        group = ServiceOptionGroup.objects.create(
            service=service,
            name="Pasta termiczna",
            selection_type=ServiceOptionGroup.SelectionType.SINGLE,
            is_required=True,
        )
        ServiceOption.objects.create(
            group=group,
            name="Pasta standardowa",
        )

        response = self.client.post(
            reverse("service_configurator", args=[service.id]),
            {"action": "price_only"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wybierz opcję w grupie")
        self.assertContains(response, "Pasta termiczna")
        self.assertNotContains(response, "Cena po konfiguracji")

    def test_required_option_group_blocks_order_creation(self):
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=100,
            base_price_max=150,
        )
        group = ServiceOptionGroup.objects.create(
            service=service,
            name="Pasta termiczna",
            selection_type=ServiceOptionGroup.SelectionType.SINGLE,
            is_required=True,
        )
        ServiceOption.objects.create(
            group=group,
            name="Pasta standardowa",
        )

        response = self.client.post(
            reverse("service_configurator", args=[service.id]),
            {
                "customer_name": "Jan Kowalski",
                "customer_email": "jan@example.com",
                "customer_phone": "123456789",
                "customer_consent": "on",
                "device_type": ServiceOrder.DeviceType.LAPTOP,
                "device_brand": "Lenovo",
                "device_model": "ThinkPad T14",
                "device_issue_description": "Laptop nie uruchamia się po aktualizacji.",
                "action": "create_order",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ServiceOrder.objects.count(), 0)
        self.assertContains(response, "Wybierz opcję w grupie")
        self.assertContains(response, "Pasta termiczna")

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        SITE_URL="https://serwis.test",
    )
    def test_required_option_group_accepts_selected_option(self):
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=100,
            base_price_max=150,
        )
        group = ServiceOptionGroup.objects.create(
            service=service,
            name="Pasta termiczna",
            selection_type=ServiceOptionGroup.SelectionType.SINGLE,
            is_required=True,
        )
        option = ServiceOption.objects.create(
            group=group,
            name="Pasta premium",
            price_delta_min=30,
            price_delta_max=50,
        )

        response = self.client.post(
            reverse("service_configurator", args=[service.id]),
            {
                f"group_{group.id}": str(option.id),
                "customer_name": "Jan Kowalski",
                "customer_email": "jan@example.com",
                "customer_phone": "123456789",
                "customer_consent": "on",
                "device_type": ServiceOrder.DeviceType.LAPTOP,
                "device_brand": "Lenovo",
                "device_model": "ThinkPad T14",
                "device_issue_description": "Laptop nie uruchamia się po aktualizacji.",
                "action": "create_order",
            },
        )

        self.assertEqual(response.status_code, 302)
        item = ServiceOrderItem.objects.get()
        self.assertEqual(item.calculated_price_min, 130)
        self.assertEqual(item.calculated_price_max, 200)
        order = ServiceOrder.objects.get()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Potwierdzenie przyjęcia zlecenia", mail.outbox[0].subject)
        self.assertIn(f"https://serwis.test/track/?order_number={order.order_number}", mail.outbox[0].body)

    def test_create_order_rolls_back_when_snapshot_option_save_fails(self):
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=100,
            base_price_max=150,
        )
        group = ServiceOptionGroup.objects.create(
            service=service,
            name="Pasta termiczna",
            selection_type=ServiceOptionGroup.SelectionType.SINGLE,
            is_required=True,
        )
        option = ServiceOption.objects.create(
            group=group,
            name="Pasta premium",
            price_delta_min=30,
            price_delta_max=50,
        )

        with patch(
            "orders.services.ServiceOrderItemOption.objects.create",
            side_effect=RuntimeError("snapshot failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("service_configurator", args=[service.id]),
                    {
                        f"group_{group.id}": str(option.id),
                        "customer_name": "Jan Kowalski",
                        "customer_email": "jan@example.com",
                        "customer_phone": "123456789",
                        "customer_consent": "on",
                        "device_type": ServiceOrder.DeviceType.LAPTOP,
                        "device_brand": "Lenovo",
                        "device_model": "ThinkPad T14",
                        "device_issue_description": "Laptop nie uruchamia się po aktualizacji.",
                        "action": "create_order",
                    },
                )

        self.assertEqual(ServiceOrder.objects.count(), 0)
        self.assertEqual(ServiceOrderItem.objects.count(), 0)
        self.assertEqual(ServiceOrderItemOption.objects.count(), 0)
        self.assertEqual(AuditLog.objects.count(), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_create_order_is_saved_when_confirmation_email_fails(self):
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=100,
            base_price_max=150,
        )

        with patch("orders.emails.send_mail", side_effect=RuntimeError("SMTP down")):
            response = self.client.post(
                reverse("service_configurator", args=[service.id]),
                {
                    "customer_name": "Jan Kowalski",
                    "customer_email": "jan@example.com",
                    "customer_phone": "123456789",
                    "customer_consent": "on",
                    "device_type": ServiceOrder.DeviceType.LAPTOP,
                    "device_brand": "Lenovo",
                    "device_model": "ThinkPad T14",
                    "device_issue_description": "Laptop nie uruchamia się po aktualizacji.",
                    "action": "create_order",
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ServiceOrder.objects.count(), 1)
        self.assertEqual(ServiceOrderItem.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(response, "Zlecenie zostało zapisane")
        self.assertContains(response, "nie udało się wysłać wiadomości e-mail")

    def test_price_calculation_shows_configured_duration(self):
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=100,
            base_price_max=150,
            base_duration_minutes=90,
        )
        group = ServiceOptionGroup.objects.create(
            service=service,
            name="Zakres",
            selection_type=ServiceOptionGroup.SelectionType.SINGLE,
        )
        option = ServiceOption.objects.create(
            group=group,
            name="Pełna diagnostyka",
            duration_delta_minutes=30,
        )

        response = self.client.post(
            reverse("service_configurator", args=[service.id]),
            {
                f"group_{group.id}": str(option.id),
                "action": "price_only",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Szacowany czas usługi")
        self.assertContains(response, "120 min")

    def test_manual_pricing_service_does_not_show_zero_price_as_offer(self):
        service = Service.objects.create(
            name="Nietypowa sprawa",
            pricing_mode=Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
            base_price_min=0,
            base_price_max=0,
            base_duration_minutes=0,
        )
        group = ServiceOptionGroup.objects.create(
            service=service,
            name="Rodzaj problemu",
            selection_type=ServiceOptionGroup.SelectionType.SINGLE,
        )
        option = ServiceOption.objects.create(
            group=group,
            name="Nie wiem - prosze o diagnoze",
        )

        response = self.client.post(
            reverse("service_configurator", args=[service.id]),
            {
                f"group_{group.id}": str(option.id),
                "action": "price_only",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wycena po diagnozie")
        self.assertContains(response, "Cena i czas realizacji")
        self.assertNotContains(response, "Cena po konfiguracji")
        self.assertNotContains(response, "0,00 - 0,00")

    def test_manual_pricing_mode_is_saved_in_order_snapshot(self):
        service = Service.objects.create(
            name="Nietypowa sprawa",
            pricing_mode=Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
            base_price_min=0,
            base_price_max=0,
            base_duration_minutes=0,
        )

        response = self.client.post(
            reverse("service_configurator", args=[service.id]),
            {
                "customer_name": "Jan Kowalski",
                "customer_email": "jan@example.com",
                "customer_phone": "123456789",
                "customer_consent": "on",
                "device_type": ServiceOrder.DeviceType.LAPTOP,
                "device_brand": "Lenovo",
                "device_model": "ThinkPad T14",
                "device_issue_description": "Problem nie pasuje do katalogu.",
                "action": "create_order",
            },
        )

        self.assertEqual(response.status_code, 302)
        item = ServiceOrderItem.objects.get()
        self.assertEqual(
            item.pricing_mode_snapshot,
            Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
        )
        self.assertTrue(item.requires_manual_pricing)

    def test_create_order_ignores_options_from_other_service(self):
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=100,
            base_price_max=150,
        )
        group = ServiceOptionGroup.objects.create(
            service=service,
            name="Pasta termiczna",
            selection_type=ServiceOptionGroup.SelectionType.SINGLE,
        )

        other_service = Service.objects.create(
            name="Naprawa telefonu",
            base_price_min=50,
            base_price_max=80,
        )
        other_group = ServiceOptionGroup.objects.create(
            service=other_service,
            name="Tryb realizacji",
            selection_type=ServiceOptionGroup.SelectionType.SINGLE,
        )
        foreign_option = ServiceOption.objects.create(
            group=other_group,
            name="Ekspres",
            price_delta_min=999,
            price_delta_max=999,
        )

        response = self.client.post(
            reverse("service_configurator", args=[service.id]),
            {
                f"group_{group.id}": str(foreign_option.id),
                "customer_name": "Jan Kowalski",
                "customer_email": "jan@example.com",
                "customer_phone": "123456789",
                "customer_consent": "on",
                "device_type": ServiceOrder.DeviceType.LAPTOP,
                "device_brand": "Lenovo",
                "device_model": "ThinkPad T14",
                "device_issue_description": "Laptop nie uruchamia się po aktualizacji.",
                "action": "create_order",
            },
        )

        self.assertEqual(response.status_code, 302)
        order = ServiceOrder.objects.get()
        self.assertEqual(order.device_type, ServiceOrder.DeviceType.LAPTOP)
        self.assertEqual(order.device_brand, "Lenovo")
        self.assertEqual(order.device_model, "ThinkPad T14")
        self.assertEqual(order.device_issue_description, "Laptop nie uruchamia się po aktualizacji.")
        item = ServiceOrderItem.objects.get()
        self.assertEqual(item.calculated_price_min, service.base_price_min)
        self.assertEqual(item.calculated_price_max, service.base_price_max)
        self.assertEqual(ServiceOrderItemOption.objects.count(), 0)

    def test_create_order_requires_consent_and_valid_contact_data(self):
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=100,
            base_price_max=150,
        )

        response = self.client.post(
            reverse("service_configurator", args=[service.id]),
            {
                "customer_name": "J1",
                "customer_email": "niepoprawny-email",
                "customer_phone": "12",
                "action": "create_order",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ServiceOrder.objects.count(), 0)
        self.assertContains(response, "Podaj poprawne imię i nazwisko.")
        self.assertContains(response, "Podaj poprawny adres e-mail.")
        self.assertContains(response, "Podaj poprawny numer telefonu.")
        self.assertContains(response, "Potwierdź zgodę na kontakt w sprawie zlecenia.")
        self.assertContains(response, "Wybierz typ urządzenia.")
        self.assertContains(response, "Podaj markę urządzenia.")
        self.assertContains(response, "Opisz krótko problem z urządzeniem.")

    def test_customer_can_add_public_attachment_when_creating_order(self):
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=100,
            base_price_max=150,
        )
        uploaded_file = SimpleUploadedFile(
            "usterka.png",
            b"png-content",
            content_type="image/png",
        )

        response = self.client.post(
            reverse("service_configurator", args=[service.id]),
            {
                "customer_name": "Jan Kowalski",
                "customer_email": "jan@example.com",
                "customer_phone": "123456789",
                "customer_consent": "on",
                "device_type": ServiceOrder.DeviceType.LAPTOP,
                "device_brand": "Lenovo",
                "device_model": "ThinkPad T14",
                "device_issue_description": "Laptop nie uruchamia się po aktualizacji.",
                "attachment": uploaded_file,
                "action": "create_order",
            },
        )

        self.assertEqual(response.status_code, 302)
        order = ServiceOrder.objects.get()
        attachment = ServiceOrderAttachment.objects.get(order=order)
        self.assertEqual(attachment.visibility, ServiceOrderAttachment.Visibility.PUBLIC)
        self.assertEqual(attachment.original_name, "usterka.png")
        self.assertIsNone(attachment.uploaded_by)
        self.assertTrue(
            AuditLog.objects.filter(
                order=order,
                action=AuditLog.Action.ATTACHMENT_ADDED,
                performed_by=None,
            ).exists()
        )

        track_response = self.client.post(
            reverse("track_order"),
            {
                "order_number": order.order_number,
                "email": order.customer_email,
            },
        )

        self.assertContains(track_response, "Załączniki z serwisu")
        self.assertContains(track_response, "usterka.png")

    def test_customer_cannot_add_unsupported_attachment_when_creating_order(self):
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=100,
            base_price_max=150,
        )
        uploaded_file = SimpleUploadedFile(
            "plik.exe",
            b"binary",
            content_type="application/octet-stream",
        )

        response = self.client.post(
            reverse("service_configurator", args=[service.id]),
            {
                "customer_name": "Jan Kowalski",
                "customer_email": "jan@example.com",
                "customer_phone": "123456789",
                "customer_consent": "on",
                "device_type": ServiceOrder.DeviceType.LAPTOP,
                "device_brand": "Lenovo",
                "device_model": "ThinkPad T14",
                "device_issue_description": "Laptop nie uruchamia się po aktualizacji.",
                "attachment": uploaded_file,
                "action": "create_order",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ServiceOrder.objects.count(), 0)
        self.assertContains(response, "Dozwolone są tylko pliki JPG, PNG lub PDF.")
