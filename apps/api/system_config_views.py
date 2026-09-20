"""
GET /api/v1/system/get_systems_config/ — cấu hình hệ thống đã đăng ký.

Port từ Laravel ``SystemController::getSystemsConfig``: hiện tại Laravel
cũng chỉ là placeholder trả mảng rỗng (TODO trong service gốc) — port khung
endpoint để frontend không gãy, logic thật sẽ bổ sung sau.
"""

from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from libs.responses import success_response


class GetSystemsConfigView(APIView):
	"""GET /api/v1/system/get_systems_config/ — cấu hình hệ thống của user."""

	permission_classes = [permissions.IsAuthenticated]
	throttle_classes = [ScopedRateThrottle]
	throttle_scope = "core"
	http_method_names = ["get", "options"]

	@extend_schema(
		tags=["System"],
		responses={200: dict},
	)
	def get(self, request):
		# TODO: port logic thật từ Laravel GetSystemsConfigService (hiện trả [])
		return success_response(data={})