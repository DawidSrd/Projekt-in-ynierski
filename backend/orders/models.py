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
