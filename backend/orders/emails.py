import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


def build_tracking_url(order_number):
    return f"{settings.SITE_URL}/track/?{urlencode({'order_number': order_number})}"


def get_order_device_label(order):
    parts = [
        order.get_device_type_display() if order.device_type else "",
        order.device_brand,
        order.device_model,
    ]
    return " ".join(part for part in parts if part) or "brak danych"


def build_order_confirmation_email(order):
    tracking_url = build_tracking_url(order.order_number)
    subject = f"Potwierdzenie przyjęcia zlecenia {order.order_number}"
    message = (
        "Dzień dobry,\n\n"
        "dziękujemy za zgłoszenie w serwisie komputerowym.\n\n"
        f"Numer zlecenia: {order.order_number}\n"
        f"Status: {order.get_status_display()}\n"
        f"Urządzenie: {get_order_device_label(order)}\n"
        f"Opis problemu: {order.device_issue_description}\n\n"
        "Status zlecenia możesz sprawdzić tutaj:\n"
        f"{tracking_url}\n\n"
        "Do weryfikacji podaj numer zlecenia oraz e-mail albo telefon użyty w formularzu.\n\n"
        "Pozdrawiamy,\n"
        "Serwis komputerowy"
    )
    return subject, message


def build_order_cancellation_email(order):
    tracking_url = build_tracking_url(order.order_number)
    subject = f"Anulowanie zlecenia {order.order_number}"
    message = (
        "Dzień dobry,\n\n"
        f"Twoje zlecenie {order.order_number} zostało anulowane.\n\n"
        f"Aktualny status: {order.get_status_display()}\n\n"
        "Szczegóły zlecenia możesz sprawdzić tutaj:\n"
        f"{tracking_url}\n\n"
        "Pozdrawiamy,\n"
        "Serwis komputerowy"
    )
    return subject, message


def build_status_change_email(order):
    tracking_url = build_tracking_url(order.order_number)
    subject = f"Zmiana statusu zlecenia {order.order_number}"
    message = (
        "Dzień dobry,\n\n"
        f"Status Twojego zlecenia {order.order_number} został zmieniony.\n\n"
        f"Aktualny status: {order.get_status_display()}\n"
        f"Urządzenie: {get_order_device_label(order)}\n\n"
        "Szczegóły i historię zlecenia możesz sprawdzić tutaj:\n"
        f"{tracking_url}\n\n"
        "Pozdrawiamy,\n"
        "Serwis komputerowy"
    )
    return subject, message


def send_customer_email(subject, message, recipient):
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[recipient],
        )
    except Exception:
        logger.debug("Nie udało się wysłać wiadomości e-mail do %s.", recipient, exc_info=True)
        return False
    return True
