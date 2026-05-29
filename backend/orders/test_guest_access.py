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

class GuestAccessCancellationTests(TestCase):
    def setUp(self):
        self.order = ServiceOrder.objects.create(
            customer_name="Jan Kowalski",
            customer_email="jan@example.com",
            customer_phone="123456789",
        )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        SITE_URL="https://serwis.test",
    )
    def test_customer_can_cancel_new_order(self):
        response = self.client.post(
            reverse("track_order"),
            {
                "action": "cancel_order",
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, ServiceOrderStatus.CANCELED)
        self.assertTrue(
            AuditLog.objects.filter(
                order=self.order,
                action=AuditLog.Action.ORDER_CANCELED,
                old_value=ServiceOrderStatus.NEW,
                new_value=ServiceOrderStatus.CANCELED,
                performed_by=None,
            ).exists()
        )
        self.assertContains(response, "Zlecenie zostało anulowane.")
        self.assertContains(response, "Zlecenie anulowane")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(
            f"https://serwis.test/track/?order_number={self.order.order_number}",
            mail.outbox[0].body,
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_customer_cancel_is_saved_when_email_fails(self):
        with patch("orders.emails.send_mail", side_effect=RuntimeError("SMTP down")):
            response = self.client.post(
                reverse("track_order"),
                {
                    "action": "cancel_order",
                    "order_number": self.order.order_number,
                    "email": self.order.customer_email,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, ServiceOrderStatus.CANCELED)
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(response, "Zlecenie zostało anulowane.")
        self.assertContains(response, "Nie udało się wysłać wiadomości e-mail do klienta.")

    def test_customer_cannot_cancel_order_after_service_started(self):
        self.order.status = ServiceOrderStatus.IN_PROGRESS
        self.order.save()

        response = self.client.post(
            reverse("track_order"),
            {
                "action": "cancel_order",
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, ServiceOrderStatus.IN_PROGRESS)
        self.assertFalse(
            AuditLog.objects.filter(
                order=self.order,
                action=AuditLog.Action.ORDER_CANCELED,
            ).exists()
        )
        self.assertContains(response, "Skontaktuj się telefonicznie z serwisem.")


class GuestAccessTrackingTests(TestCase):
    def setUp(self):
        self.order = ServiceOrder.objects.create(
            customer_name="Jan Kowalski",
            customer_email="jan@example.com",
            customer_phone="123456789",
        )

    def test_customer_can_track_order_with_formatted_phone_number(self):
        response = self.client.post(
            reverse("track_order"),
            {
                "order_number": self.order.order_number,
                "phone": "123 456-789",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)
        self.assertNotContains(response, "Nie znaleziono zlecenia dla podanych danych.")

    def test_customer_tracking_shows_service_scope(self):
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=120,
            base_price_max=180,
        )
        group = ServiceOptionGroup.objects.create(
            service=service,
            name="Pasta termoprzewodząca",
        )
        option = ServiceOption.objects.create(
            group=group,
            name="Pasta premium",
            price_delta_min=30,
            price_delta_max=50,
        )
        item = ServiceOrderItem.objects.create(
            order=self.order,
            service=service,
            service_name_snapshot=service.name,
            pricing_mode_snapshot=service.pricing_mode,
            base_price_min_snapshot=service.base_price_min,
            base_price_max_snapshot=service.base_price_max,
            calculated_price_min=150,
            calculated_price_max=230,
        )
        ServiceOrderItemOption.objects.create(
            order_item=item,
            option=option,
            option_name_snapshot=option.name,
            price_delta_min_snapshot=option.price_delta_min,
            price_delta_max_snapshot=option.price_delta_max,
        )

        response = self.client.post(
            reverse("track_order"),
            {
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zakres usługi")
        self.assertContains(response, "Czyszczenie laptopa")
        self.assertContains(response, "Pasta premium")
        self.assertContains(response, "150,00 - 230,00 zł")

    def test_customer_tracking_hides_internal_comments_attachments_and_workflow_events(self):
        technician = User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        ServiceOrderComment.objects.create(
            order=self.order,
            visibility=ServiceOrderComment.Visibility.INTERNAL,
            content="Tylko dla serwisu: klient zdenerwowany.",
            created_by=technician,
        )
        ServiceOrderAttachment.objects.create(
            order=self.order,
            visibility=ServiceOrderAttachment.Visibility.INTERNAL,
            file=SimpleUploadedFile(
                "notatka.pdf",
                b"internal-content",
                content_type="application/pdf",
            ),
            original_name="notatka.pdf",
            uploaded_by=technician,
        )
        AuditLog.objects.create(
            order=self.order,
            entity_type=AuditLog.EntityType.SERVICE_ORDER,
            entity_id=self.order.id,
            action=AuditLog.Action.TECHNICIAN_ASSIGNED,
            new_value="technik",
            performed_by=technician,
        )
        AuditLog.objects.create(
            order=self.order,
            entity_type=AuditLog.EntityType.SERVICE_ORDER,
            entity_id=self.order.id,
            action=AuditLog.Action.ATTACHMENT_ADDED,
            new_value="visibility=INTERNAL; file=notatka.pdf",
            performed_by=technician,
        )

        response = self.client.post(
            reverse("track_order"),
            {
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Tylko dla serwisu")
        self.assertNotContains(response, "notatka.pdf")
        self.assertNotContains(response, "Przypisano technika")
        self.assertNotContains(response, "Dodano załącznik")


class GuestAccessRepairAcceptanceTests(TestCase):
    def setUp(self):
        self.order = ServiceOrder.objects.create(
            customer_name="Jan Kowalski",
            customer_email="jan@example.com",
            customer_phone="123456789",
            diagnosis="Uszkodzony dysk SSD.",
            final_price=350,
        )

    def test_customer_can_accept_repair(self):
        response = self.client.post(
            reverse("track_order"),
            {
                "action": "accept_repair",
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertTrue(self.order.customer_accepted_repair)
        self.assertTrue(
            AuditLog.objects.filter(
                order=self.order,
                action=AuditLog.Action.REPAIR_ACCEPTED,
                old_value="False",
                new_value="True",
                performed_by=None,
            ).exists()
        )
        self.assertContains(response, "Naprawa została zaakceptowana.")
        self.assertContains(response, "Zaakceptowana przez klienta")
        self.assertContains(response, "Klient zaakceptował naprawę")

    def test_customer_cannot_accept_repair_without_final_price(self):
        self.order.final_price = None
        self.order.save()

        response = self.client.post(
            reverse("track_order"),
            {
                "action": "accept_repair",
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertFalse(self.order.customer_accepted_repair)
        self.assertFalse(
            AuditLog.objects.filter(
                order=self.order,
                action=AuditLog.Action.REPAIR_ACCEPTED,
            ).exists()
        )
        self.assertContains(response, "Akceptacja naprawy nie jest jeszcze dostępna.")

    def test_zero_final_price_is_visible_for_customer(self):
        self.order.final_price = 0
        self.order.save()

        response = self.client.post(
            reverse("track_order"),
            {
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Koszt końcowy")
        self.assertContains(response, "0,00")
