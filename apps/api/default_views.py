"""
GET /api/v1/default/get_systems/ — thông tin hệ thống của user.

Port từ Laravel ``DefaultController::getSystems``:
    1. Cây header đã đăng ký của user (Group → Pages → Headers, lọc theo
       đăng ký công khai của bộ phận + riêng của user) — apps/info/services.py
    2. Notifycation (tạm thời rỗng — Laravel cũng trả [])
    3. User setting (tạm thời object rỗng — Laravel cũng trả {})
"""

from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.info.services import get_registered_structure
from libs.responses import success_response


class GetRegisteredSystemsView(APIView):
	"""GET /api/v1/default/get_systems/ — cây hệ thống đã đăng ký của user."""

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