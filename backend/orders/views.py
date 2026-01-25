from django.shortcuts import render
from .models import ServiceOrder, ServiceOrderComment


def track_order(request):
    """
    Guest access: śledzenie zlecenia bez logowania.

    GET  -> pokazuje formularz
    POST -> weryfikuje dane i pokazuje wynik
    """
    context = {"result": None, "error": None}

    if request.method == "POST":
        order_number = (request.POST.get("order_number") or "").strip().upper()
        email = (request.POST.get("email") or "").strip().lower()
        phone = (request.POST.get("phone") or "").strip()

        # Minimalne wymaganie: numer zlecenia + (email albo phone)
        if not order_number or (not email and not phone):
            context["error"] = "Podaj numer zlecenia oraz e-mail lub numer telefonu."
            return render(request, "orders/track_order.html", context)

        # Szukamy zlecenia
        order = ServiceOrder.objects.filter(order_number=order_number).first()

        # Bezpieczeństwo: nie mówimy, czy numer jest poprawny.
        if not order:
            context["error"] = "Nie znaleziono zlecenia dla podanych danych."
            return render(request, "orders/track_order.html", context)

        # Weryfikacja: email lub telefon musi pasować do zlecenia
        email_ok = email and (order.customer_email.lower() == email)
        phone_ok = phone and (order.customer_phone == phone)

        if not (email_ok or phone_ok):
            context["error"] = "Nie znaleziono zlecenia dla podanych danych."
            return render(request, "orders/track_order.html", context)

        public_comments = ServiceOrderComment.objects.filter(
            order=order,
            visibility=ServiceOrderComment.Visibility.PUBLIC,
        ).order_by("created_at")

        context["result"] = {
            "order_number": order.order_number,
            "status": order.get_status_display(),
            "estimated_completion_at": order.estimated_completion_at,
            "comments": public_comments,
        }

    return render(request, "orders/track_order.html", context)
