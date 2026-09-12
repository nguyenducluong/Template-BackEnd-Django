from django.urls import path

from . import views

urlpatterns = [
    path("", views.SystemDispatchView.as_view(), name="system-dispatch"),
]
