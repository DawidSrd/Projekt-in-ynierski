import secrets
import string

from django.db import models
from django.utils import timezone

from .choices import ServiceOrderStatus


class Service(models.Model):
    class PricingMode(models.TextChoices):
        CONFIGURABLE = "CONFIGURABLE", "Wycena z konfiguratora"
        MANUAL_AFTER_DIAGNOSIS = "MANUAL_AFTER_DIAGNOSIS", "Wycena po diagnozie"

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Widełki są potrzebne, bo koszt zależy od konfiguracji albo diagnozy.
    pricing_mode = models.CharField(
        max_length=30,
        choices=PricingMode.choices,
        default=PricingMode.CONFIGURABLE,
        db_index=True,
    )

    base_price_min = models.DecimalField(max_digits=10, decimal_places=2)
    base_price_max = models.DecimalField(max_digits=10, decimal_places=2)

    base_duration_minutes = models.PositiveIntegerField(default=60)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "usługa"
        verbose_name_plural = "Usługi"

    def __str__(self) -> str:
        return self.name

    @property
    def requires_manual_pricing(self) -> bool:
        return self.pricing_mode == self.PricingMode.MANUAL_AFTER_DIAGNOSIS


class ServiceOptionGroup(models.Model):
    class SelectionType(models.TextChoices):
        SINGLE = "SINGLE", "Jednokrotny wybór"
        MULTI = "MULTI", "Wielokrotny wybór"

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="option_groups",
    )
    name = models.CharField(max_length=200)

    # Typ wyboru mówi formularzowi, czy z tej sekcji można wybrać jedną czy kilka opcji.
    selection_type = models.CharField(
        max_length=10,
        choices=SelectionType.choices,
        default=SelectionType.SINGLE,
    )
    is_required = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "opcja usługi"
        verbose_name_plural = "Opcje usług"

    def __str__(self) -> str:
        return f"{self.service.name} / {self.name}"


class ServiceOption(models.Model):
    group = models.ForeignKey(
        ServiceOptionGroup,
        on_delete=models.CASCADE,
        related_name="options",
    )
    name = models.CharField(max_length=200)

    # Konfigurator dolicza te kwoty do ceny bazowej usługi.
    price_delta_min = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_delta_max = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    duration_delta_minutes = models.IntegerField(default=0)

    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "wariant opcji"
        verbose_name_plural = "Warianty opcji"

    def __str__(self) -> str:
        return f"{self.group.name} / {self.name}"


def generate_order_number(prefix: str = "SRV", length: int = 8) -> str:
    # Publiczny numer nie ujawnia wewnętrznego ID z bazy.
    alphabet = string.ascii_uppercase + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}-{random_part}"


class ServiceOrder(models.Model):
    class DeviceType(models.TextChoices):
        LAPTOP = "LAPTOP", "Laptop"
        DESKTOP = "DESKTOP", "Komputer stacjonarny"

    # Numer zlecenia służy klientowi do śledzenia sprawy bez konta.
    order_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        default=generate_order_number,
        editable=False,
    )

    # E-mail albo telefon są drugim elementem weryfikacji przy śledzeniu zlecenia.
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=30)

    device_type = models.CharField(
        max_length=20,
        choices=DeviceType.choices,
        blank=True,
        default="",
    )
    device_brand = models.CharField(max_length=100, blank=True)
    device_model = models.CharField(max_length=100, blank=True)
    device_issue_description = models.TextField(blank=True)

    diagnosis = models.TextField(blank=True)
    repair_notes = models.TextField(blank=True)
    final_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    customer_accepted_repair = models.BooleanField(default=False)
    assigned_technician = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_service_orders",
    )

    status = models.CharField(
        max_length=20,
        choices=ServiceOrderStatus.choices,
        default=ServiceOrderStatus.NEW,
        db_index=True,
    )

    # Termin wpisuje technik, bo zależy od diagnozy i dostępności części.
    estimated_completion_at = models.DateTimeField(
        "Planowany termin realizacji",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "zlecenie serwisowe"
        verbose_name_plural = "Zlecenia serwisowe"

    def can_cancel(self) -> bool:
        # Po przyjęciu sprzętu anulowanie online jest blokowane.
        return self.status == ServiceOrderStatus.NEW

    def can_accept_repair(self) -> bool:
        return (
            bool(self.diagnosis)
            and self.final_price is not None
            and not self.customer_accepted_repair
            and self.status not in [ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELED]
        )

    def is_overdue(self) -> bool:
        if not self.estimated_completion_at:
            return False

        # Zakończone i anulowane sprawy nie trafiają do przekroczonych terminów.
        if self.status in [ServiceOrderStatus.COMPLETED, ServiceOrderStatus.CANCELED]:
            return False

        return timezone.now() > self.estimated_completion_at

    def __str__(self) -> str:
        return f"ServiceOrder {self.order_number}"


class ServiceOrderComment(models.Model):
    class Visibility(models.TextChoices):
        INTERNAL = "INTERNAL", "Wewnętrzny"
        PUBLIC = "PUBLIC", "Publiczny"

    order = models.ForeignKey(
        ServiceOrder,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    created_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_order_comments",
    )

    # Tylko komentarze publiczne są widoczne w śledzeniu zlecenia.
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.INTERNAL,
        db_index=True,
    )

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "komentarz do zlecenia"
        verbose_name_plural = "Komentarze do zleceń"

    def __str__(self) -> str:
        return f"Comment({self.visibility}) for {self.order.order_number}"


class ServiceOrderAttachment(models.Model):
    class Visibility(models.TextChoices):
        INTERNAL = "INTERNAL", "Wewnętrzny"
        PUBLIC = "PUBLIC", "Publiczny"

    order = models.ForeignKey(
        ServiceOrder,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    # Załączniki wewnętrzne zostają tylko w panelu pracownika.
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.INTERNAL,
        db_index=True,
    )
    file = models.FileField(upload_to="order_attachments/%Y/%m/")
    original_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_order_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "załącznik do zlecenia"
        verbose_name_plural = "Załączniki do zleceń"

    def __str__(self) -> str:
        return f"Attachment({self.visibility}) for {self.order.order_number}"


class ServiceOrderItem(models.Model):
    order = models.ForeignKey(
        ServiceOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )

    # Snapshot chroni historyczną wycenę przed późniejszą zmianą usługi.
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    service_name_snapshot = models.CharField(max_length=200)

    pricing_mode_snapshot = models.CharField(
        max_length=30,
        choices=Service.PricingMode.choices,
        default=Service.PricingMode.CONFIGURABLE,
    )
    base_price_min_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    base_price_max_snapshot = models.DecimalField(max_digits=10, decimal_places=2)

    calculated_price_min = models.DecimalField(max_digits=10, decimal_places=2)
    calculated_price_max = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pozycja zlecenia"
        verbose_name_plural = "Pozycje zleceń"

    def __str__(self) -> str:
        return f"Item for {self.order.order_number} / {self.service_name_snapshot}"

    @property
    def requires_manual_pricing(self) -> bool:
        return self.pricing_mode_snapshot == Service.PricingMode.MANUAL_AFTER_DIAGNOSIS


class ServiceOrderItemOption(models.Model):
    order_item = models.ForeignKey(
        ServiceOrderItem,
        on_delete=models.CASCADE,
        related_name="selected_options",
    )

    # Snapshot opcji zachowuje dopłaty wybrane przy składaniu zlecenia.
    option = models.ForeignKey(
        ServiceOption,
        on_delete=models.PROTECT,
        related_name="order_item_options",
    )
    option_name_snapshot = models.CharField(max_length=200)

    price_delta_min_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    price_delta_max_snapshot = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "wybrana opcja zlecenia"
        verbose_name_plural = "Wybrane opcje zleceń"

    def __str__(self) -> str:
        return f"{self.option_name_snapshot}"


# Historia zmian zapisuje zdarzenia potrzebne do rozliczalności obsługi.
class AuditLog(models.Model):
    class EntityType(models.TextChoices):
        SERVICE_ORDER = "SERVICE_ORDER", "Zlecenie serwisowe"
        SERVICE_ORDER_COMMENT = "SERVICE_ORDER_COMMENT", "Komentarz do zlecenia"

    class Action(models.TextChoices):
        STATUS_CHANGED = "STATUS_CHANGED", "Zmiana statusu"
        COMMENT_ADDED = "COMMENT_ADDED", "Dodanie komentarza"
        ESTIMATE_SET = "ESTIMATE_SET", "Ustawienie planowanego terminu"
        ORDER_CANCELED = "ORDER_CANCELED", "Anulowanie zlecenia"
        ORDER_CREATED = "ORDER_CREATED", "Utworzenie zlecenia"
        DIAGNOSIS_UPDATED = "DIAGNOSIS_UPDATED", "Aktualizacja diagnozy"
        REPAIR_ACCEPTED = "REPAIR_ACCEPTED", "Akceptacja naprawy"
        TECHNICIAN_ASSIGNED = "TECHNICIAN_ASSIGNED", "Przypisanie technika"
        ATTACHMENT_ADDED = "ATTACHMENT_ADDED", "Dodanie załącznika"

    # Dzięki temu można szybko pobrać historię konkretnego zlecenia.
    order = models.ForeignKey(
        "orders.ServiceOrder",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="audit_logs",
        db_index=True,
    )

    entity_type = models.CharField(
        max_length=50,
        choices=EntityType.choices,
        db_index=True,
    )

    entity_id = models.PositiveIntegerField(db_index=True)

    action = models.CharField(
        max_length=50,
        choices=Action.choices,
        db_index=True,
    )

    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)

    performed_by = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "wpis historii zmian"
        verbose_name_plural = "Historia zmian"

    def __str__(self) -> str:
        return f"{self.entity_type}#{self.entity_id} {self.action}"
