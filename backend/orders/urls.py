from django.urls import path
from . import views

urlpatterns = [
    path("track/", views.track_order, name="track_order"),
    path("services/", views.service_catalog, name="service_catalog"),
    path("services/<int:service_id>/", views.service_configurator, name="service_configurator"),
]

path(
    "order-created/<str:order_number>/",
    views.order_created,
    name="order_created",
),
