from django.urls import include, path

from . import views

urlpatterns = [
    # Endpoint lấy thông tin init hệ thống: /api/v1/systems/init_data
    path("default/", include("apps.systems.default.urls")),
    path("init_data", views.SystemDispatchView.as_view(), name="system-dispatch"),
    # path("")
]
