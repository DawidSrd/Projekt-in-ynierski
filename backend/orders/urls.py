from django.urls import path
from . import views
from django.shortcuts import render

urlpatterns = [
    path("track/", views.track_order, name="track_order"),
    path("services/", views.service_catalog, name="service_catalog"),
    path("services/<int:service_id>/", views.service_configurator, name="service_configurator"),
    path("order-created/<str:order_number>/", views.order_created, name="order_created"),
]

def order_created(request, order_number: str):
    """
    Strona potwierdzenia utworzenia zlecenia (PRG redirect – GET).
    """
    return render(
        request,
        "orders/order_created.html",
        {
            "order_number": order_number,
        },
    )