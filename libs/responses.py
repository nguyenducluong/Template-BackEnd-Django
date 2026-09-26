from django.utils.translation import gettext as _
from rest_framework.response import Response


def success_response(data=None, message=None, status=200, meta=None):
    """Standard success response format."""
    if message is None:
        message = _("Success")
    response = {
        "success": True,
        "data": data,
        "message": message,
        "errors": None,
        "meta": meta or {"status_code": status},
    }
    return Response(response, status=status)


def error_response(message=None, errors=None, status=400, meta=None):
    """Standard error response format."""
    if message is None:
        message = _("Error")
    response = {
        "success": False,
        "data": None,
        "message": message,
        "errors": errors,
        "meta": meta or {"status_code": status},
    }
    return Response(response, status=status)


def created_response(data=None, message=None):
    """Response for resource creation (201)."""
    if message is None:
        message = _("Resource created successfully")
    return success_response(data=data, message=message, status=201)


def deleted_response(data=None, message=None):
    """Response cho thao tác xoá thành công — 200 + envelope (không dùng 204).

    Lý do KHÔNG dùng 204: ``libs.middlewares.encryption.EncryptionMiddleware``
    bỏ qua response 204 (không có body để mã hoá) ⇒ client đang bật mã hoá nhận
    response rỗng, không giải mã được. Trả 200 + envelope giữ contract đồng nhất.

    Method dùng để xoá là ``POST`` (không dùng DELETE — xem libs/http_policy.py).
    """
    if message is None:
        message = _("Deleted successfully")
    return success_response(data=data, message=message, status=200)


def no_content_response():
    """DEPRECATED — giữ lại để không phá import cũ.

    Trước đây trả 204 cho thao tác xoá; đã thay bằng ``deleted_response()``
    (200 + envelope) để response luôn được mã hoá/parse đồng nhất.
    """
    return deleted_response()


class EnvelopeMixin:
    """Wrap DRF ViewSet/ViewSetMixin responses in the standard envelope.

    Apply to ReadOnlyModelViewSet / ModelViewSet so list/retrieve/create/
    update/destroy all return {success, data, message, errors, meta}.
    """

    def _envelope(self, response, message=None):
        if response.status_code >= 400:
            return error_response(
                message=getattr(response, "data", None) or _("Error"),
                status=response.status_code,
            )
        # Pagination responses already carry the envelope shape -- pass through
        body = getattr(response, "data", None)
        if isinstance(body, dict) and "success" in body:
            return response
        return success_response(data=response.data, message=message)

    def list(self, request, *args, **kwargs):
        return self._envelope(super().list(request, *args, **kwargs))

    def retrieve(self, request, *args, **kwargs):
        return self._envelope(super().retrieve(request, *args, **kwargs))

    def create(self, request, *args, **kwargs):
        """POST tạo mới → 201 (KHÔNG dùng PUT/PATCH/DELETE để ghi dữ liệu)."""
        response = self._envelope(super().create(request, *args, **kwargs), _("Resource created successfully"))
        response.status_code = 201
        # _envelope() tạo meta với status_code=200 → cập nhật lại cho khớp HTTP status
        if isinstance(getattr(response, "data", None), dict) and isinstance(response.data.get("meta"), dict):
            response.data["meta"]["status_code"] = 201
        return response

    def update(self, request, *args, **kwargs):
        return self._envelope(super().update(request, *args, **kwargs))

    def partial_update(self, request, *args, **kwargs):
        return self._envelope(super().partial_update(request, *args, **kwargs))

    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)