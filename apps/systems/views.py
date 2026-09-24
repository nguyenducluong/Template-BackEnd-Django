"""
System Headers Dispatcher — điều phối mọi request của SystemHeader.

Endpoint duy nhất:
    POST /api/v1/systems/init_data

POST body:
    {
        "header_id": 1,          # int — khớp apps.info.models.SystemHeader.id
        "func": "search",        # str — tên hàm trong systems_details/{header_id}/views.py
        "params": { ... }        # dict — tham số nghiệp vụ (search, pagination, sort...)
    }

Cơ chế:
    1. Lấy SystemHeader theo header_id (phải is_use=True).
    2. Import module ``apps.systems.systems_details.{header_id}.views``.
    3. Gọi hàm tên ``func`` với chữ ký (request, header=..., params=...).
    4. Hàm tự trả về DRF Response (thường qua libs.responses.success_response).
"""

import importlib
import json
import logging
from types import SimpleNamespace

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.views import APIView

from apps.info.models import SystemHeader
from apps.info.permissions import DEMO_HEADER_IDS, HasHeaderPermission
from libs.auth.throttling import ScopedRateThrottle
from libs.responses import error_response

# Re-export để code cũ (nếu có) import từ apps.systems.views vẫn chạy.
__all__ = ['SystemDispatchView', 'DEMO_HEADER_IDS', 'make_demo_header']


def make_demo_header(header_id):
	"""Dựng header demo tại chỗ (không get_object_or_404 DB)."""
	return SimpleNamespace(
		id=header_id,
		header_vi=f'Header Demo {header_id}',
		header_en=f'Header Demo {header_id}',
		header_kr=f'데모 헤더 {header_id}',
		view_vi='Demo',
		is_mobile=False,
	)

class SystemDispatchView(APIView):
    """POST /api/v1/systems/init_data — điều phối theo {header_id, func} trong body."""

    # IsAuthenticated → 401 khi chưa đăng nhập; HasHeaderPermission → 403 khi
    # user không có quyền truy cập header (quyền T1 — apps/info/permissions.py).
    permission_classes = [permissions.IsAuthenticated, HasHeaderPermission]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "systems"
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["Systems"],
        request={
            "application/json": {
                "type": "object",
                "properties": {
                    "header_id": {"type": "integer"},
                    "func": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["header_id", "func"],
            }
        },
        responses={200: dict},
    )
    def post(self, request):
        payload = request.data or {}
        header_id = payload.get("header_id")
        func = payload.get("func")
        params = payload.get("params") or {}

        # ---- Chuẩn hoá input của request MULTIPART (có file đính kèm) ----
        # multipart không mang kiểu dữ liệu: mọi field là chuỗi, trong đó `params`
        # được FE gửi dạng JSON string để giữ nguyên cấu trúc dict
        # (xem STD/src/axios/axios.jsx::build_form_data).
        if isinstance(params, str):
            try:
                params = json.loads(params or "{}")
            except ValueError:
                return error_response(
                    message=_("Field 'params' must be a valid JSON object."),
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if isinstance(header_id, str) and header_id.strip().lstrip("-").isdigit():
            header_id = int(header_id)

        # ---- Validate input ----
        if not header_id or not func:
            return error_response(
                message=_("Fields 'header_id' and 'func' are required."),
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(header_id, int):
            return error_response(
                message=_("Field 'header_id' must be an integer."),
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(params, dict):
            return error_response(
                message=_("Field 'params' must be an object."),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---- Lấy SystemHeader ----
        # Header demo: dựng tại chỗ, không tra DB (bypass HeaderPermission DB).
        if header_id in DEMO_HEADER_IDS:
            header = make_demo_header(header_id)
        else:
            try:
                header = get_object_or_404(SystemHeader, pk=header_id, is_use=True)
            except SystemHeader.DoesNotExist:
                return error_response(
                    message=_("System header not found"),
                    status=status.HTTP_404_NOT_FOUND,
                )

        # ---- Import module của hệ thống ----
        module_path = f"apps.systems.systems_details.{header_id}.views"
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError:
            return error_response(
                message=_("System module not implemented for this header."),
                status=status.HTTP_404_NOT_FOUND,
            )

        # ---- Gọi func ----
        handler = getattr(module, func, None)
        if not callable(handler):
            return error_response(
                message=_("Function '%(func)s' not found in system %(id)s.")
                % {"func": func, "id": header.id},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            return handler(request, header=header, params=params)
        except Exception:
            return error_response(
                message=_("System function execution failed."),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
