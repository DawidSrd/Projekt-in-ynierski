from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .choices import ServiceOrderStatus
from .models import (
    AuditLog,
    Service,
    ServiceOption,
    ServiceOptionGroup,
    ServiceOrder,
    ServiceOrderComment,
    ServiceOrderItem,
    ServiceOrderItemOption,
)


class HomePageTests(TestCase):
    def test_anonymous_home_page_shows_client_entry_points(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zgłoś naprawę lub sprawdź status zlecenia")
        self.assertContains(response, "Jak możemy pomóc?")
        self.assertContains(response, "Katalog usług")
        self.assertContains(response, "Sprawdź status zlecenia")
        self.assertContains(response, 'href="/services/"')
        self.assertContains(response, 'href="/track/"')
        self.assertContains(response, 'href="/staff/login/"')
        self.assertNotContains(response, "Utworzenie zlecenia")
        self.assertNotContains(response, "Śledzenie statusu")
        self.assertNotContains(response, "Panel technika")
        self.assertNotContains(response, "Admin")
        self.assertNotContains(response, 'href="/tech/dashboard/"')
        self.assertNotContains(response, 'href="/admin/"')

    def test_staff_user_sees_technician_navigation_only(self):
        User.objects.create_user(
            username="technik",
            password="testpass123",
            is_staff=True,
        )
        self.client.login(username="technik", password="testpass123")

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel technika")
        self.assertContains(response, 'href="/tech/dashboard/"')
        self.assertContains(response, 'action="/staff/logout/"')
        self.assertNotContains(response, "Admin")
        self.assertNotContains(response, 'href="/admin/"')

    def test_superuser_sees_technician_and_admin_navigation(self):
        User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        self.client.login(username="admin", password="testpass123")

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel technika")
        self.assertContains(response, "Admin")
        self.assertContains(response, 'href="/tech/dashboard/"')
        self.assertContains(response, 'href="/admin/"')

    def test_admin_index_uses_custom_dashboard(self):
        User.objects.create_superuser(
            username="admin",
            password="testpass123",
            email="admin@example.com",
        )
        self.client.login(username="admin", password="testpass123")

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Panel administratora")
        self.assertContains(response, "Administracja serwisem")
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
        self.assertIn("/staff/login/", response["Location"])

    def test_tech_dashboard_shows_counts_ready_orders_and_status_filter(self):
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
            {"status": ServiceOrderStatus.READY},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard_counts"]["new"], 1)
        self.assertEqual(response.context["dashboard_counts"]["ready"], 1)
        self.assertEqual(response.context["dashboard_counts"]["in_progress"], 1)
        self.assertEqual(response.context["selected_status"], ServiceOrderStatus.READY)
        self.assertContains(response, "Gotowe")
        self.assertContains(response, "Zlecenia: Gotowe do odbioru")
        self.assertContains(response, "Anna Nowak")
        self.assertContains(response, "Szczegóły")
        self.assertContains(response, 'class="orders-table"')

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
        self.assertContains(response, "Snapshot usługi")
        self.assertContains(response, "Czyszczenie laptopa")
        self.assertContains(response, "Pasta premium")
        self.assertContains(response, "150.00 - 230.00 zł")

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
                "action": "update_order",
                "status": ServiceOrderStatus.RECEIVED,
                "estimated_completion_at": "2026-05-03 16:30",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, ServiceOrderStatus.RECEIVED)
        self.assertIsNotNone(self.order.estimated_completion_at)
        self.assertEqual(len(mail.outbox), 0)
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

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_staff_can_send_status_email_when_checkbox_is_selected(self):
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
                "estimated_completion_at": "",
                "notify_customer": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, ServiceOrderStatus.RECEIVED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.order.customer_email])
        self.assertContains(response, "klient otrzymał wiadomość e-mail")

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

    def test_staff_can_add_public_comment_visible_in_tracking(self):
        User.objects.create_user(
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


class GuestAccessCancellationTests(TestCase):
    def setUp(self):
        self.order = ServiceOrder.objects.create(
            customer_name="Jan Kowalski",
            customer_email="jan@example.com",
            customer_phone="123456789",
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
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
                "customer_consent": "on",
                "action": "create_order",
            },
        )

        self.assertEqual(response.status_code, 302)
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
