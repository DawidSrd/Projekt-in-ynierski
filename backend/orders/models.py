from django.db import models
from .choices import ServiceOrderStatus
import secrets
import string




class Service(models.Model):
    """
    Usługa widoczna w katalogu dla klienta, np. "Czyszczenie laptopa".

    Trzymamy widełki cenowe (min/max), bo wymaganie mówi o cenie "od-do"
    lub bazowej + dodatkach (wtedy min=max).
    """
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    base_price_min = models.DecimalField(max_digits=10, decimal_places=2)
    base_price_max = models.DecimalField(max_digits=10, decimal_places=2)

    base_duration_minutes = models.PositiveIntegerField(default=60)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class ServiceOptionGroup(models.Model):
    """
    Grupa opcji dla danej usługi, np. "Pasta termiczna", "Tryb realizacji".

    selection_type:
    - SINGLE: klient wybiera jedną opcję z grupy
    - MULTI: klient może zaznaczyć wiele opcji
    """
    class SelectionType(models.TextChoices):
        SINGLE = "SINGLE", "Jednokrotny wybór"
        MULTI = "MULTI", "Wielokrotny wybór"

    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name="option_groups",
    )
    name = models.CharField(max_length=200)

    selection_type = models.CharField(
        max_length=10,
        choices=SelectionType.choices,
        default=SelectionType.SINGLE,
    )
    is_required = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.service.name} / {self.name}"


class ServiceOption(models.Model):
    """
    Konkretna opcja w grupie, np. "Pasta standard", "Pasta premium".

    price_delta_min/max: o ile zmienia się cena (widełki) po wybraniu opcji.
    duration_delta_minutes: o ile zmienia się czas realizacji.
    """
    group = models.ForeignKey(
        ServiceOptionGroup,
        on_delete=models.CASCADE,
        related_name="options",
    )
    name = models.CharField(max_length=200)

    price_delta_min = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_delta_max = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    duration_delta_minutes = models.IntegerField(default=0)

    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.group.name} / {self.name}"


def generate_order_number(prefix: str = "SRV", length: int = 8) -> str:
    """
    Generuje publiczny numer zlecenia w formacie: SRV-XXXXXXXX.
    Używa bezpiecznego generatora losowego (secrets).
    """
    alphabet = string.ascii_uppercase + string.digits  # A-Z + 0-9
    random_part = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}-{random_part}"


class ServiceOrder(models.Model):
    """
    Encja zlecenia serwisowego (Service Ticket).
    Przechowuje dane identyfikacyjne klienta oraz aktualny status workflow.
    """

    # Identyfikator biznesowy (publiczny) - używany w guest access / komunikacji z klientem
    order_number = models.CharField(
        max_length=20,
        unique=True,
        db_index=True,
        default=generate_order_number,
        editable=False,
    )


    # Dane kontaktowe klienta (do powiadomień + weryfikacji w guest access)
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=30)

    # Aktualny status workflow zlecenia
    status = models.CharField(
        max_length=20,
        choices=ServiceOrderStatus.choices,
        default=ServiceOrderStatus.NEW,
        db_index=True,
    )

    # Estymacja zakończenia ustawiana ręcznie przez technika (opcjonalna)
    estimated_completion_at = models.DateTimeField(null=True, blank=True)

    # Metadane audytowe (kiedy utworzono i kiedy modyfikowano rekord)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def can_cancel(self) -> bool:
        """
        Reguła biznesowa: anulowanie dozwolone tylko w statusie NEW.
        """
        return self.status == ServiceOrderStatus.NEW

    def __str__(self) -> str:
        return f"ServiceOrder {self.order_number}"

class ServiceOrderComment(models.Model):
    """
    Komentarz do zlecenia.
    visibility rozdziela komentarze wewnętrzne (dla serwisu) i publiczne (dla klienta).
    """

    class Visibility(models.TextChoices):
        INTERNAL = "INTERNAL", "Wewnętrzny"
        PUBLIC = "PUBLIC", "Publiczny"

    order = models.ForeignKey(
        ServiceOrder,
        on_delete=models.CASCADE,
        related_name="comments",
    )

    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.INTERNAL,
        db_index=True,
    )

    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Comment({self.visibility}) for {self.order.order_number}"
    

class ServiceOrderItem(models.Model):
    """
    Pozycja zlecenia - snapshot usługi i wyceny w momencie złożenia zamówienia.
    Dzięki temu zmiana cennika w przyszłości nie zmienia historycznego zlecenia.
    """
    order = models.ForeignKey(
        ServiceOrder,
        on_delete=models.CASCADE,
        related_name="items",
    )

    # Referencja do usługi + snapshot nazwy (na wypadek zmiany nazwy w CMS)
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    service_name_snapshot = models.CharField(max_length=200)

    # Snapshot ceny bazowej usługi
    base_price_min_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    base_price_max_snapshot = models.DecimalField(max_digits=10, decimal_places=2)

    # Cena policzona po konfiguracji (wynikowa) - widełki
    calculated_price_min = models.DecimalField(max_digits=10, decimal_places=2)
    calculated_price_max = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Item for {self.order.order_number} / {self.service_name_snapshot}"


class ServiceOrderItemOption(models.Model):
    """
    Snapshot wybranej opcji w pozycji zlecenia.
    Trzymamy też snapshot nazwy i wpływu na cenę.
    """
    order_item = models.ForeignKey(
        ServiceOrderItem,
        on_delete=models.CASCADE,
        related_name="selected_options",
    )

    option = models.ForeignKey(
        ServiceOption,
        on_delete=models.PROTECT,
        related_name="order_item_options",
    )
    option_name_snapshot = models.CharField(max_length=200)

    price_delta_min_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    price_delta_max_snapshot = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self) -> str:
        return f"{self.option_name_snapshot}"

   
class AuditLog(models.Model):
    """
    Dziennik zdarzeń systemowych (audit trail).
    Rejestruje zmianę stanu obiektów domenowych, np. zleceń.
    """

    class EntityType(models.TextChoices):
        SERVICE_ORDER = "SERVICE_ORDER", "Zlecenie serwisowe"
        SERVICE_ORDER_COMMENT = "SERVICE_ORDER_COMMENT", "Komentarz do zlecenia"

    class Action(models.TextChoices):
        STATUS_CHANGED = "STATUS_CHANGED", "Zmiana statusu"
        COMMENT_ADDED = "COMMENT_ADDED", "Dodanie komentarza"
        ESTIMATE_SET = "ESTIMATE_SET", "Ustawienie estymacji"
        ORDER_CANCELED = "ORDER_CANCELED", "Anulowanie zlecenia"
        ORDER_CREATED = "ORDER_CREATED", "Utworzenie zlecenia"


    # Powiązanie wpisu audytowego z konkretnym zleceniem (do widoku inline)
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

    def __str__(self) -> str:
        return f"{self.entity_type}#{self.entity_id} {self.action}"
