"""
GET /api/v1/define/options_authentication/ — nhãn UI trang Auth.

Port từ Laravel ``DefineAppController::getDefineApp``: trả object `init`
(title/button/input/divider) theo ngôn ngữ client (Accept-Language).
Public endpoint — frontend gọi trước khi đăng nhập.
"""

from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.views import APIView

from apps.api.define_data import build_init_options
from libs.responses import success_response


class DefineAppView(APIView):
	"""GET /api/v1/define/options_authentication/ — trả nhãn UI trang Auth."""

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