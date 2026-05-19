import re
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import ServiceOrder


PHONE_PATTERN = re.compile(r"^\+?[0-9\s-]{7,20}$")
ALLOWED_ATTACHMENT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024


def normalize_phone_number(phone_number):
    return re.sub(r"\D", "", phone_number or "")


def get_customer_order_errors(customer_name, customer_email, customer_phone, customer_consent):
    errors = []

    if len(customer_name) < 3 or any(char.isdigit() for char in customer_name):
        errors.append("Podaj poprawne imię i nazwisko.")

    try:
        validate_email(customer_email)
    except ValidationError:
        errors.append("Podaj poprawny adres e-mail.")

    phone_digits = normalize_phone_number(customer_phone)
    if not PHONE_PATTERN.match(customer_phone) or len(phone_digits) < 7 or len(phone_digits) > 15:
        errors.append("Podaj poprawny numer telefonu.")

    if not customer_consent:
        errors.append("Potwierdź zgodę na kontakt w sprawie zlecenia.")

    return errors


def get_device_order_errors(device_type, device_brand, device_issue_description):
    errors = []

    if device_type not in dict(ServiceOrder.DeviceType.choices):
        errors.append("Wybierz typ urządzenia.")

    if len(device_brand) < 2:
        errors.append("Podaj markę urządzenia.")

    if len(device_issue_description) < 5:
        errors.append("Opisz krótko problem z urządzeniem.")

    return errors


def get_attachment_error(uploaded_file):
    if uploaded_file is None:
        return "Wybierz plik do dodania."

    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        return "Dozwolone są tylko pliki JPG, PNG lub PDF."

    if uploaded_file.size > MAX_ATTACHMENT_SIZE:
        return "Plik może mieć maksymalnie 5 MB."

    return None
