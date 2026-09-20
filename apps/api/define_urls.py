from django.urls import path

from apps.api.define_views import DefineAppView

app_name = "define"

urlpatterns = [
	path("options_authentication", DefineAppView.as_view(), name="define-options-authentication"),
]