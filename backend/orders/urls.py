from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("staff/login/", views.staff_login, name="staff_login"),
    path("staff/logout/", views.staff_logout, name="staff_logout"),
    path("track/", views.track_order, name="track_order"),
    path("attachments/<int:attachment_id>/", views.attachment_download, name="attachment_download"),
    path("services/", views.service_catalog, name="service_catalog"),
    path("services/<int:service_id>/", views.service_configurator, name="service_configurator"),
    path("order-created/<str:order_number>/", views.order_created, name="order_created"),
    path("tech/dashboard/", views.tech_dashboard, name="tech_dashboard"),
    path("tech/orders/new/", views.tech_order_create, name="tech_order_create"),
    path("tech/orders/<str:order_number>/delete/", views.tech_order_delete, name="tech_order_delete"),
    path("tech/orders/<str:order_number>/", views.tech_order_detail, name="tech_order_detail"),
]
