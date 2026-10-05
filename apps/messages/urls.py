"""Routing cua app messages - CHI 1 endpoint POST (dispatcher)."""

from django.urls import path

from . import views

urlpatterns = [
	path('dispatch', views.MessagesDispatchView.as_view(), name='messages-dispatch'),
]
