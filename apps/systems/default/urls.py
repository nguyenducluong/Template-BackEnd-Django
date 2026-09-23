from django.urls import path

from apps.systems.default import views

urlpatterns = [
	# GET /api/v1/system/default/get_systems — cây hệ thống đã đăng ký của user
	path("get_systems", views.GetRegisteredSystemsView.as_view(), name="get-systems"),
	# GET /api/v1/system/default/options_authentication — nhãn UI trang Auth (vi/en/kr, public)
	path("options_authentication", views.DefineAppView.as_view(), name="options-authentication"),
]
