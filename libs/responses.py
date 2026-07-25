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
        "meta": meta or {},
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