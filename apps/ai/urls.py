from django.urls import path

from . import views

urlpatterns = [
    path("chat", views.AIChatView.as_view(), name="ai-chat"),
    path("faq", views.FAQListView.as_view(), name="ai-faq"),
]
