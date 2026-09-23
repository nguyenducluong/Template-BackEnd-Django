"""
System Headers Dispatcher — điều phối mọi request của SystemHeader.

Endpoint duy nhất:
    POST /api/v1/systems/

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
import logging

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.views import APIView

from apps.info.models import SystemHeader
from libs.auth.throttling import ScopedRateThrottle
from libs.responses import error_response

class SystemDispatchView(APIView):
    """POST /api/v1/systems/ — điều phối theo {header_id, func} trong body."""

    permission_classes = [permissions.IsAuthenticated]
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
        try:
            header = get_object_or_404(SystemHeader, pk=header_id, is_use=True)
        except SystemHeader.DoesNotExist:
            return error_response(
                message=_("System header not found."),
                status=status.HTTP_404_NOT_FOUND,
            )

        # ---- Import module của hệ thống ----
        module_path = f"apps.systems.systems_details.{header.id}.views"
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
