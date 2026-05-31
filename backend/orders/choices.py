from django.db import models

class ServiceOrderStatus(models.TextChoices):
    NEW = "NEW", "Nowe"
    RECEIVED = "RECEIVED", "Przyjęte"
    IN_PROGRESS = "IN_PROGRESS", "W toku"
    WAITING_FOR_PARTS = "WAITING_FOR_PARTS", "Czeka na części"
    READY = "READY", "Gotowe do odbioru"
    COMPLETED = "COMPLETED", "Zakończone"
    CANCELED = "CANCELED", "Anulowane"


# Mapa przejść ogranicza zmianę statusu do kolejnych etapów pracy serwisu.
SERVICE_ORDER_STATUS_TRANSITIONS = {
    ServiceOrderStatus.NEW: (
        ServiceOrderStatus.RECEIVED,
        ServiceOrderStatus.CANCELED,
    ),
    ServiceOrderStatus.RECEIVED: (
        ServiceOrderStatus.IN_PROGRESS,
    ),
    ServiceOrderStatus.IN_PROGRESS: (
        ServiceOrderStatus.WAITING_FOR_PARTS,
        ServiceOrderStatus.READY,
    ),
    ServiceOrderStatus.WAITING_FOR_PARTS: (
        ServiceOrderStatus.IN_PROGRESS,
        ServiceOrderStatus.READY,
    ),
    ServiceOrderStatus.READY: (
        ServiceOrderStatus.COMPLETED,
    ),
    ServiceOrderStatus.COMPLETED: (),
    ServiceOrderStatus.CANCELED: (),
}


def can_change_order_status(current_status: str, new_status: str) -> bool:
    if current_status == new_status:
        return True

    return new_status in SERVICE_ORDER_STATUS_TRANSITIONS.get(current_status, ())


def get_available_order_status_choices(current_status: str):
    status_labels = dict(ServiceOrderStatus.choices)
    available_statuses = (
        current_status,
        *SERVICE_ORDER_STATUS_TRANSITIONS.get(current_status, ()),
    )

    return tuple(
        (status, status_labels[status])
        for status in available_statuses
    )
