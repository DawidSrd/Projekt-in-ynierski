from django.db import models

class ServiceOrderStatus(models.TextChoices):
    NEW = "NEW", "Nowe"
    RECEIVED = "RECEIVED", "Przyjęte"
    IN_PROGRESS = "IN_PROGRESS", "W toku"
    WAITING_FOR_PARTS = "WAITING_FOR_PARTS", "Czeka na części"
    READY = "READY", "Gotowe do odbioru"
    COMPLETED = "COMPLETED", "Zakończone"
    CANCELED = "CANCELED", "Anulowane"
