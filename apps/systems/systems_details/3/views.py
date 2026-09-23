"""
Header 1 — Waiting for IQC (입고검사대상 및 결과입력).

- Func handlers cho dispatcher ``init_data`` (apps.systems) — re-export từ base_system.
- SystemDetailsView: DRF endpoint riêng của header — POST /api/v1/systems/details/1.
"""

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.views import APIView

from apps.info.models import SystemHeader
from apps.systems.systems_details.base_system import (  # noqa: F401
	action,
	chart,
	dashboard,
	definition,
	details,
	download,
	search,
)
from .serializers import Header3DetailsRequestSerializer
from libs.auth.throttling import ScopedRateThrottle
from libs.responses import error_response

import logging

logger = logging.getLogger("apps")


class Header3DetailsView(APIView):
	"""POST /api/v1/systems/details/1 — dữ liệu view chi tiết của Header 1."""

	permission_classes = [permissions.IsAuthenticated]
	throttle_classes = [ScopedRateThrottle]
	throttle_scope = "systems"
	http_method_names = ["post", "options"]

	@extend_schema(
		tags=["Systems Details"],
		request=Header3DetailsRequestSerializer,
		responses={200: dict},
	)
	def post(self, request):
		serializer = Header3DetailsRequestSerializer(data=request.data or {})
		serializer.is_valid(raise_exception=True)
		body = serializer.validated_data

		header = get_object_or_404(SystemHeader, pk=1, is_use=True)
		try:
			params = {"scope": body["scope"], "query": body["query"]}
			return details(request, header=header, params=params)
		except Exception:
			return error_response(
				message=_("System function execution failed."),
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)

