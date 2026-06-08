from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .choices import ServiceOrderStatus, can_change_order_status
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

class TechnicianViewsTests(TestCase):
    def setUp(self):
        self.order = ServiceOrder.objects.create(
            customer_name="Jan Kowalski",
            customer_email="jan@example.com",
            customer_phone="123456789",
            device_type=ServiceOrder.DeviceType.LAPTOP,
            device_brand="Lenovo",
            device_model="ThinkPad T14",
            device_issue_description="Nie uruchamia się po aktualizacji.",
        )

    def test_tech_dashboard_requires_staff_login(self):
        response = self.client.get(reverse("tech_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/staff/login/", response["Location"])

    def test_tech_order_create_requires_staff_login(self):
        response = self.client.get(reverse("tech_order_create"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/staff/login/", response["Location"])

    def test_tech_dashboard_shows_counts_ready_orders_and_status_filter(self):
        technician = User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        ServiceOrder.objects.create(
            customer_name="Anna Nowak",
            customer_email="anna@example.com",
            customer_phone="111222333",
            status=ServiceOrderStatus.READY,
        )
        ServiceOrder.objects.create(
            customer_name="Piotr Zielinski",
            customer_email="piotr@example.com",
            customer_phone="444555666",
            status=ServiceOrderStatus.RECEIVED,
        )

        response = self.client.get(
            reverse("tech_dashboard"),
            {"scope": "all", "status": ServiceOrderStatus.READY},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_counts"]["new"], 1)
        self.assertEqual(response.context["dashboard_counts"]["ready"], 1)
        self.assertEqual(response.context["dashboard_counts"]["in_progress"], 1)
        self.assertEqual(response.context["selected_status"], ServiceOrderStatus.READY)
        self.assertContains(response, "Gotowe")
        self.assertContains(response, "Panel technika")
        self.assertContains(response, "Nowe zgłoszenie")
        self.assertContains(response, "Wyniki filtrowania")
        self.assertContains(response, "Status: Gotowe do odbioru.")
        self.assertContains(response, "Anna Nowak")
        self.assertContains(response, "Szczegóły")
        self.assertContains(response, 'class="orders-table"')
        self.assertContains(response, "Urządzenie")
        self.assertContains(response, "Planowany termin")
        self.assertContains(response, "Przekroczone terminy")
        self.assertNotContains(response, "Estymacja")

    def test_tech_dashboard_shows_canceled_orders_after_status_filter(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        canceled_order = ServiceOrder.objects.create(
            customer_name="Anulowany Klient",
            customer_email="anulowany@example.com",
            customer_phone="111222333",
            status=ServiceOrderStatus.CANCELED,
        )

        response = self.client.get(
            reverse("tech_dashboard"),
            {"scope": "all", "status": ServiceOrderStatus.CANCELED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_status"], ServiceOrderStatus.CANCELED)
        self.assertIn(
            ServiceOrderStatus.CANCELED,
            [code for code, _label in response.context["status_choices"]],
        )
        self.assertIn(canceled_order, response.context["dashboard_orders"])
        self.assertContains(response, "Anulowany Klient")
        self.assertContains(response, "Anulowane")

    def test_tech_dashboard_can_filter_by_search_and_device_type(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        ServiceOrder.objects.create(
            customer_name="Anna Nowak",
            customer_email="anna@example.com",
            customer_phone="111222333",
            device_type=ServiceOrder.DeviceType.DESKTOP,
            device_brand="Dell",
            device_model="OptiPlex",
            device_issue_description="Komputer wyłącza się pod obciążeniem.",
        )

        response = self.client.get(
            reverse("tech_dashboard"),
            {
                "scope": "all",
                "q": "ThinkPad",
                "device_type": ServiceOrder.DeviceType.LAPTOP,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["search_query"], "ThinkPad")
        self.assertEqual(response.context["selected_device_type"], ServiceOrder.DeviceType.LAPTOP)
        self.assertContains(response, "Wyniki filtrowania")
        self.assertContains(response, "Jan Kowalski")
        self.assertContains(response, "ThinkPad T14")
        self.assertNotContains(response, "Anna Nowak")
        self.assertNotContains(response, "OptiPlex")

    def test_tech_dashboard_can_filter_overdue_orders(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        self.order.status = ServiceOrderStatus.IN_PROGRESS
        self.order.estimated_completion_at = timezone.now() - timedelta(days=1)
        self.order.save()
        ServiceOrder.objects.create(
            customer_name="Anna Nowak",
            customer_email="anna@example.com",
            customer_phone="111222333",
            status=ServiceOrderStatus.IN_PROGRESS,
            device_type=ServiceOrder.DeviceType.LAPTOP,
            device_brand="Lenovo",
            device_model="IdeaPad",
            estimated_completion_at=timezone.now() + timedelta(days=1),
        )
        ServiceOrder.objects.create(
            customer_name="Piotr Zielinski",
            customer_email="piotr@example.com",
            customer_phone="444555666",
            status=ServiceOrderStatus.COMPLETED,
            device_type=ServiceOrder.DeviceType.LAPTOP,
            device_brand="Lenovo",
            device_model="ThinkPad X1",
            estimated_completion_at=timezone.now() - timedelta(days=2),
        )

        response = self.client.get(
            reverse("tech_dashboard"),
            {
                "scope": "all",
                "overdue": "1",
                "q": "ThinkPad",
                "device_type": ServiceOrder.DeviceType.LAPTOP,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["selected_overdue"])
        self.assertEqual(response.context["dashboard_counts"]["overdue"], 1)
        self.assertContains(response, "Termin: przekroczony.")
        self.assertContains(response, "Jan Kowalski")
        self.assertContains(response, "ThinkPad T14")
        self.assertNotContains(response, "Anna Nowak")
        self.assertNotContains(response, "Piotr Zielinski")

    def test_tech_dashboard_can_show_only_current_technician_orders(self):
        technician = User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        other_technician = User.objects.create_user(
            username="technik2",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        self.order.assigned_technician = technician
        self.order.save()
        ServiceOrder.objects.create(
            customer_name="Anna Nowak",
            customer_email="anna@example.com",
            customer_phone="111222333",
            assigned_technician=other_technician,
        )

        response = self.client.get(
            reverse("tech_dashboard"),
            {"scope": "mine"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["scope"], "mine")
        self.assertContains(response, "Moje zlecenia")
        self.assertContains(response, "Jan Kowalski")
        self.assertNotContains(response, "Anna Nowak")

    def test_tech_dashboard_can_show_all_orders(self):
        technician = User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        other_technician = User.objects.create_user(
            username="technik2",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        self.order.assigned_technician = technician
        self.order.save()
        ServiceOrder.objects.create(
            customer_name="Anna Nowak",
            customer_email="anna@example.com",
            customer_phone="111222333",
            assigned_technician=other_technician,
        )

        response = self.client.get(
            reverse("tech_dashboard"),
            {"scope": "all"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["scope"], "all")
        self.assertContains(response, "Jan Kowalski")
        self.assertContains(response, "Anna Nowak")

    def test_tech_dashboard_unassigned_scope_shows_quick_claim_action(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.get(
            reverse("tech_dashboard"),
            {"scope": "unassigned"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Przejmij")
        self.assertContains(response, 'name="action" value="claim_order"')
        self.assertContains(response, f'action="/tech/orders/{self.order.order_number}/"')

    def test_tech_dashboard_empty_state_has_useful_shortcuts(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.get(
            reverse("tech_dashboard"),
            {"scope": "mine"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Brak zleceń w tym widoku")
        self.assertContains(response, 'href="/tech/dashboard/?scope=unassigned"')
        self.assertContains(response, 'href="/tech/dashboard/?scope=all"')

    def test_staff_can_create_received_order_from_backoffice(self):
        technician = User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        service = Service.objects.create(
            name="Diagnostyka w punkcie",
            base_price_min=80,
            base_price_max=150,
        )

        response = self.client.post(
            reverse("tech_order_create"),
            {
                "service_id": str(service.id),
                "customer_name": "Adam Serwisowy",
                "customer_email": "adam@example.com",
                "customer_phone": "501222333",
                "device_type": ServiceOrder.DeviceType.DESKTOP,
                "device_brand": "Dell",
                "device_model": "OptiPlex",
                "device_issue_description": "Komputer nie uruchamia się w punkcie serwisowym.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        order = ServiceOrder.objects.get(customer_email="adam@example.com")
        self.assertEqual(order.status, ServiceOrderStatus.RECEIVED)
        self.assertEqual(order.assigned_technician, technician)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.get().service, service)
        self.assertTrue(
            AuditLog.objects.filter(
                order=order,
                action=AuditLog.Action.ORDER_CREATED,
                performed_by=technician,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                order=order,
                action=AuditLog.Action.TECHNICIAN_ASSIGNED,
                performed_by=technician,
                new_value="technik",
            ).exists()
        )
        self.assertContains(response, "Zlecenie zostało utworzone.")
        self.assertContains(response, order.order_number)
        self.assertContains(response, "Przyjęte")

    def test_tech_order_detail_shows_service_snapshot_and_price(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        service = Service.objects.create(
            name="Czyszczenie laptopa",
            base_price_min=120,
            base_price_max=180,
        )
        group = ServiceOptionGroup.objects.create(
            service=service,
            name="Pasta termiczna",
            selection_type=ServiceOptionGroup.SelectionType.SINGLE,
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

        response = self.client.get(
            reverse("tech_order_detail", args=[self.order.order_number]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Karta obsługi zlecenia serwisowego")
        self.assertContains(response, "Obsługa zlecenia")
        self.assertContains(response, "Zakres usługi i wycena")
        self.assertContains(response, "Zakres usługi zapisany przy utworzeniu zlecenia.")
        self.assertContains(response, "Urządzenie")
        self.assertContains(response, "Laptop / Lenovo ThinkPad T14")
        self.assertContains(response, "Nie uruchamia się po aktualizacji.")
        self.assertContains(response, "Czyszczenie laptopa")
        self.assertContains(response, "Pasta premium")
        self.assertContains(response, "150,00 - 230,00 zł")

    def test_staff_can_delete_order_from_detail_page(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        detail_response = self.client.get(
            reverse("tech_order_detail", args=[self.order.order_number])
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "Usuń zgłoszenie")
        self.assertContains(
            detail_response,
            reverse("tech_order_delete", args=[self.order.order_number]),
        )
        self.assertContains(detail_response, "Czy na pewno chcesz usunąć to zgłoszenie?")

        delete_response = self.client.post(
            reverse("tech_order_delete", args=[self.order.order_number])
        )

        self.assertEqual(delete_response.status_code, 302)
        self.assertEqual(delete_response["Location"], reverse("tech_dashboard"))
        self.assertFalse(ServiceOrder.objects.filter(pk=self.order.pk).exists())

    def test_tech_order_detail_hides_price_for_manual_pricing_snapshot(self):
        technician = User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        service = Service.objects.create(
            name="Nietypowa sprawa",
            pricing_mode=Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
            base_price_min=0,
            base_price_max=0,
            base_duration_minutes=0,
        )
        ServiceOrderItem.objects.create(
            order=self.order,
            service=service,
            service_name_snapshot=service.name,
            pricing_mode_snapshot=Service.PricingMode.MANUAL_AFTER_DIAGNOSIS,
            base_price_min_snapshot=0,
            base_price_max_snapshot=0,
            calculated_price_min=0,
            calculated_price_max=0,
        )

        response = self.client.get(
            reverse("tech_order_detail", args=[self.order.order_number]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Wycena po diagnozie")
        self.assertNotContains(response, "0,00 - 0,00")

    def test_staff_can_claim_unassigned_order(self):
        technician = User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.post(
            reverse("tech_order_detail", args=[self.order.order_number]),
            {
                "action": "claim_order",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.assigned_technician, technician)
        self.assertTrue(
            AuditLog.objects.filter(
                order=self.order,
                action=AuditLog.Action.TECHNICIAN_ASSIGNED,
                old_value="",
                new_value="technik",
                performed_by=technician,
            ).exists()
        )
        self.assertContains(response, "Zlecenie zostało przypisane do Ciebie.")
        self.assertContains(response, "Prowadzący technik")
        self.assertContains(response, "technik")

    def test_staff_can_add_public_attachment_visible_in_tracking(self):
        technician = User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        uploaded_file = SimpleUploadedFile(
            "diagnoza.pdf",
            b"test-pdf-content",
            content_type="application/pdf",
        )

        response = self.client.post(
            reverse("tech_order_detail", args=[self.order.order_number]),
            {
                "action": "add_attachment",
                "visibility": ServiceOrderAttachment.Visibility.PUBLIC,
                "file": uploaded_file,
            },
        )

        self.assertEqual(response.status_code, 200)
        attachment = ServiceOrderAttachment.objects.get(order=self.order)
        self.assertEqual(attachment.visibility, ServiceOrderAttachment.Visibility.PUBLIC)
        self.assertEqual(attachment.original_name, "diagnoza.pdf")
        self.assertEqual(attachment.uploaded_by, technician)
        self.assertTrue(
            AuditLog.objects.filter(
                order=self.order,
                action=AuditLog.Action.ATTACHMENT_ADDED,
            ).exists()
        )

        self.client.logout()
        track_response = self.client.post(
            reverse("track_order"),
            {
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )

        self.assertContains(track_response, "Załączniki z serwisu")
        self.assertContains(track_response, "diagnoza.pdf")

    def test_staff_cannot_add_unsupported_attachment(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")
        uploaded_file = SimpleUploadedFile(
            "skrypt.exe",
            b"binary",
            content_type="application/octet-stream",
        )

        response = self.client.post(
            reverse("tech_order_detail", args=[self.order.order_number]),
            {
                "action": "add_attachment",
                "visibility": ServiceOrderAttachment.Visibility.INTERNAL,
                "file": uploaded_file,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ServiceOrderAttachment.objects.count(), 0)
        self.assertContains(response, "Dozwolone są tylko pliki JPG, PNG lub PDF.")

    def test_public_attachment_download_requires_verified_order(self):
        attachment = ServiceOrderAttachment.objects.create(
            order=self.order,
            visibility=ServiceOrderAttachment.Visibility.PUBLIC,
            file=SimpleUploadedFile(
                "diagnoza.pdf",
                b"test-pdf-content",
                content_type="application/pdf",
            ),
            original_name="diagnoza.pdf",
        )

        response = self.client.get(reverse("attachment_download", args=[attachment.id]))
        self.assertEqual(response.status_code, 404)

        track_response = self.client.post(
            reverse("track_order"),
            {
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )
        self.assertContains(track_response, reverse("attachment_download", args=[attachment.id]))
        self.assertNotContains(track_response, attachment.file.url)

        download_response = self.client.get(reverse("attachment_download", args=[attachment.id]))
        self.assertEqual(download_response.status_code, 200)

    def test_internal_attachment_is_available_only_for_staff(self):
        attachment = ServiceOrderAttachment.objects.create(
            order=self.order,
            visibility=ServiceOrderAttachment.Visibility.INTERNAL,
            file=SimpleUploadedFile(
                "notatka.pdf",
                b"internal-content",
                content_type="application/pdf",
            ),
            original_name="notatka.pdf",
        )

        self.client.post(
            reverse("track_order"),
            {
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )

        anonymous_response = self.client.get(reverse("attachment_download", args=[attachment.id]))
        self.assertEqual(anonymous_response.status_code, 404)

        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        staff_response = self.client.get(reverse("attachment_download", args=[attachment.id]))
        self.assertEqual(staff_response.status_code, 200)

    def test_staff_can_update_order_status_and_estimate(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.post(
            reverse("tech_order_detail", args=[self.order.order_number]),
            {
                "action": "update_order",
                "status": ServiceOrderStatus.RECEIVED,
                "estimated_completion_at": "2026-05-03T16:30",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, ServiceOrderStatus.RECEIVED)
        self.assertIsNotNone(self.order.estimated_completion_at)
        self.assertTrue(
            AuditLog.objects.filter(
                order=self.order,
                action=AuditLog.Action.STATUS_CHANGED,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                order=self.order,
                action=AuditLog.Action.ESTIMATE_SET,
            ).exists()
        )
        self.assertContains(response, "Planowany termin realizacji")
        self.assertContains(response, 'type="datetime-local"')
        self.assertContains(response, 'value="2026-05-03T16:30"')
        self.assertNotContains(response, "Estymacja")

    def test_staff_can_update_diagnosis_and_final_price_visible_for_customer(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.post(
            reverse("tech_order_detail", args=[self.order.order_number]),
            {
                "action": "update_diagnosis",
                "diagnosis": "Uszkodzony dysk SSD.",
                "repair_notes": "Wymieniono dysk i zainstalowano system.",
                "final_price": "350.00",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.diagnosis, "Uszkodzony dysk SSD.")
        self.assertEqual(self.order.repair_notes, "Wymieniono dysk i zainstalowano system.")
        self.assertEqual(str(self.order.final_price), "350.00")
        self.assertFalse(self.order.customer_accepted_repair)
        self.assertTrue(
            AuditLog.objects.filter(
                order=self.order,
                action=AuditLog.Action.DIAGNOSIS_UPDATED,
            ).exists()
        )

        self.client.logout()
        track_response = self.client.post(
            reverse("track_order"),
            {
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )

        self.assertContains(track_response, "Diagnoza i rozliczenie")
        self.assertContains(track_response, "Uszkodzony dysk SSD.")
        self.assertContains(track_response, "Wymieniono dysk i zainstalowano system.")
        self.assertContains(track_response, "350,00 zł")
        self.assertContains(track_response, "Oczekuje na decyzję")
        self.assertContains(track_response, "Akceptuję naprawę")
        self.assertContains(track_response, "Aktualizacja diagnozy i rozliczenia")

        self.client.login(username="technik", password="testpass123")
        acceptance_response = self.client.post(
            reverse("tech_order_detail", args=[self.order.order_number]),
            {"action": "register_repair_acceptance"},
        )

        self.assertEqual(acceptance_response.status_code, 200)
        self.order.refresh_from_db()
        self.assertTrue(self.order.customer_accepted_repair)
        self.assertTrue(
            AuditLog.objects.filter(
                order=self.order,
                action=AuditLog.Action.REPAIR_ACCEPTED,
                performed_by__username="technik",
            ).exists()
        )
        self.assertContains(acceptance_response, "Zgoda klienta została zarejestrowana.")
        self.assertContains(acceptance_response, "Zaakceptowana przez klienta")

        response = self.client.post(
            reverse("tech_order_detail", args=[self.order.order_number]),
            {
                "action": "update_diagnosis",
                "diagnosis": "Zmieniona diagnoza.",
                "final_price": "400.00",
            },
        )
        self.order.refresh_from_db()
        self.assertFalse(self.order.customer_accepted_repair)
        self.assertContains(response, "Akceptacja klienta została wycofana.")

    def test_staff_cannot_save_negative_final_price(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.post(
            reverse("tech_order_detail", args=[self.order.order_number]),
            {
                "action": "update_diagnosis",
                "diagnosis": "Test",
                "repair_notes": "",
                "final_price": "-10",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertIsNone(self.order.final_price)
        self.assertContains(response, "Koszt końcowy nie może być ujemny.")

    def test_staff_cannot_skip_status_workflow(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.post(
            reverse("tech_order_detail", args=[self.order.order_number]),
            {
                "action": "update_order",
                "status": ServiceOrderStatus.READY,
                "estimated_completion_at": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, ServiceOrderStatus.NEW)
        self.assertFalse(
            AuditLog.objects.filter(
                order=self.order,
                action=AuditLog.Action.STATUS_CHANGED,
            ).exists()
        )
        self.assertContains(response, "Taka zmiana statusu nie jest dozwolona")
        for status in (
            ServiceOrderStatus.RECEIVED,
            ServiceOrderStatus.IN_PROGRESS,
            ServiceOrderStatus.WAITING_FOR_PARTS,
            ServiceOrderStatus.READY,
        ):
            self.assertTrue(can_change_order_status(status, ServiceOrderStatus.CANCELED))

    def test_staff_can_add_public_comment_visible_in_tracking(self):
        technician = User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.post(
            reverse("tech_order_detail", args=[self.order.order_number]),
            {
                "action": "add_comment",
                "visibility": ServiceOrderComment.Visibility.PUBLIC,
                "content": "Sprzęt czeka na odbiór.",
            },
        )

        self.assertEqual(response.status_code, 200)
        comment = ServiceOrderComment.objects.get(order=self.order)
        self.assertEqual(comment.visibility, ServiceOrderComment.Visibility.PUBLIC)
        self.assertEqual(comment.content, "Sprzęt czeka na odbiór.")
        self.assertEqual(comment.created_by, technician)
        self.assertContains(response, "technik")
        self.assertTrue(
            AuditLog.objects.filter(
                order=self.order,
                entity_type=AuditLog.EntityType.SERVICE_ORDER_COMMENT,
                entity_id=comment.id,
                action=AuditLog.Action.COMMENT_ADDED,
            ).exists()
        )

        self.client.logout()
        track_response = self.client.post(
            reverse("track_order"),
            {
                "order_number": self.order.order_number,
                "email": self.order.customer_email,
            },
        )

        self.assertContains(track_response, "Sprzęt czeka na odbiór.")
        self.assertContains(track_response, "technik")
        self.assertContains(track_response, "Wiadomości z serwisu")
        self.assertContains(track_response, "Historia zlecenia")
        self.assertContains(track_response, "Laptop / Lenovo ThinkPad T14")
        self.assertContains(track_response, "Nie uruchamia się po aktualizacji.")
