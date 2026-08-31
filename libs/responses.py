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


def no_content_response():
    """Response for successful deletion (204)."""
    return Response(status=204)


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
        return self._envelope(super().create(request, *args, **kwargs), _("Resource created successfully"))

    def update(self, request, *args, **kwargs):
        return self._envelope(super().update(request, *args, **kwargs))

    def partial_update(self, request, *args, **kwargs):
        return self._envelope(super().partial_update(request, *args, **kwargs))

    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)