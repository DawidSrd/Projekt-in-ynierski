import logging

from django.core.mail import send_mail


logger = logging.getLogger(__name__)


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
