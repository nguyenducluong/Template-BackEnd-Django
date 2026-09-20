from django.urls import path

from . import health_views

urlpatterns = [
    path("", health_views.HealthCheckView.as_view(), name="health-check"),
    path("ready", health_views.ReadyCheckView.as_view(), name="ready-check"),
    path("live", health_views.LiveCheckView.as_view(), name="live-check"),
]