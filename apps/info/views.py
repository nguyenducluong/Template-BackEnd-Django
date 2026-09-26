"""
API của app `info` — 1 dispatcher duy nhất: ``POST /api/v1/info/dispatch``.

Vì sao chỉ POST (xem ``libs/http_policy.py``):
    - PUT/PATCH/DELETE bị chặn ở middleware + http_method_names + proxy.
    - Mọi thao tác (list/retrieve/structure/create/update/delete/reorder) đi
      qua cùng 1 endpoint, payload khai ``resource``/``action`` — giống pattern
      ``POST /api/v1/systems/init_data`` của app systems.
    - Partial update thay cho PATCH: ``"data": {"partial": true, ...}``.

Câu trả lời luôn là envelope ``{success, data, message, errors, meta}``.
"""

import logging

from django.utils.translation import gettext as _

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.views import APIView

from libs.auth.throttling import ScopedRateThrottle
from libs.responses import error_response

from . import dispatch as info_dispatch
from .permissions import CanWriteInfoConfig
from .serializers import InfoDispatchSerializer

logger = logging.getLogger("apps")


class InfoDispatchView(APIView):
    """POST /api/v1/info/dispatch — điều phối theo {resource, action} trong body."""

    # IsAuthenticated → 401 khi chưa đăng nhập; action GHI kiểm tra thêm
    # CanWriteInfoConfig (403) bên trong post().
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "info"
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["Info"],
        request=InfoDispatchSerializer,
        responses={200: dict, 201: dict, 400: dict, 401: dict, 403: dict, 404: dict},
    )
    def post(self, request):
        payload = request.data or {}
        if not hasattr(payload, "get"):
            return error_response(
                message=_("Payload must be a JSON object."),
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = InfoDispatchSerializer(data=payload)
        if not serializer.is_valid():
            return error_response(
                message=_("Invalid dispatch payload."),
                errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated = serializer.validated_data
        action = validated["action"]

        # Action GHI (create/update/delete/reorder) — quyền riêng, fail-closed.
        # Cây menu scope='all' cũng cần quyền này (xem dispatch.requires_write_permission).
        if info_dispatch.requires_write_permission(validated["resource"], action, validated.get("params")) and not CanWriteInfoConfig().has_permission(request, self):
            return error_response(
                message=CanWriteInfoConfig.message,
                status=status.HTTP_403_FORBIDDEN,
            )

        return info_dispatch.handle(
            resource=validated["resource"],
            action=action,
            user=request.user,
            item_id=validated.get("id"),
            data=validated.get("data") or {},
            params=validated.get("params") or {},
            language=getattr(request, "LANGUAGE_CODE", None) or "vi",
        )
