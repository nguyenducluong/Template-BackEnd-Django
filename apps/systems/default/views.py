"""
Views của Systems Default — gộp các endpoint hệ thống cũ port từ Laravel.

    GET /api/v1/system/default/get_systems              → GetRegisteredSystemsView
    GET /api/v1/system/default/options_authentication    → DefineAppView (public)

Mount in apps/api/urls.py: path("systems/default/", include("apps.systems.default.urls"))
"""

from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.info.services import get_registered_structure
from apps.systems.default.data import build_init_options
from libs.responses import success_response


class GetRegisteredSystemsView(APIView):
	"""GET /api/v1/system/default/get_systems/ — cây hệ thống đã đăng ký của user."""

	permission_classes = [permissions.IsAuthenticated]
	throttle_classes = [ScopedRateThrottle]
	throttle_scope = "core"
	http_method_names = ["get", "options"]

	@extend_schema(
		tags=["Default"],
		responses={200: dict},
	)
	def get(self, request):
		language = getattr(request, "LANGUAGE_CODE", None) or "vi"
		group_headers = get_registered_structure(request.user, language)
		return success_response(
			data={
				"group_headers": group_headers,
				"notifycation": [],
				"user_setting": {},
			}
		)


class DefineAppView(APIView):
	"""GET /api/v1/system/default/options_authentication/ — trả nhãn UI trang Auth."""

	authentication_classes = []
	permission_classes = [permissions.AllowAny]
	http_method_names = ["get", "options"]

	@extend_schema(
		tags=["Define"],
		responses={200: dict},
	)
	def get(self, request):
		# LanguageMiddleware đã chuẩn hóa LANGUAGE_CODE về vi/en/kr
		language = getattr(request, "LANGUAGE_CODE", None) or "vi"
		return success_response(data={"init": build_init_options(language)})
