from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .choices import ServiceOrderStatus
from .models import (
    AuditLog,
    Service,
    ServiceOption,
    ServiceOptionGroup,
    ServiceOrder,
    ServiceOrderItem,
    ServiceOrderItemOption,
)


class TechnicianViewsTests(TestCase):
    def setUp(self):
        self.order = ServiceOrder.objects.create(
            customer_name="Jan Kowalski",
            customer_email="jan@example.com",
            customer_phone="123456789",
        )

    def test_tech_dashboard_requires_staff_login(self):
        response = self.client.get(reverse("tech_dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
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
                "status": ServiceOrderStatus.IN_PROGRESS,
                "estimated_completion_at": "2026-05-03 16:30",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, ServiceOrderStatus.IN_PROGRESS)
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


class ServiceConfiguratorTests(TestCase):
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
                "action": "create_order",
            },
        )

        self.assertEqual(response.status_code, 302)
        item = ServiceOrderItem.objects.get()
        self.assertEqual(item.calculated_price_min, service.base_price_min)
        self.assertEqual(item.calculated_price_max, service.base_price_max)
        self.assertEqual(ServiceOrderItemOption.objects.count(), 0)
