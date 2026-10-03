import math

from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.exceptions import APIException, Throttled
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns consistent JSON error responses.
    """
    response = exception_handler(exc, context)

    if response is not None:
        message, errors = _get_error_message(exc, response)
        response.data = {
            "success": False,
            "data": None,
            "message": message,
            "errors": errors,
            "meta": {
                "status_code": response.status_code,
            },
        }
    return response


def _get_error_message(exc, response=None):
    """
    Get a human-readable, localized error message from an exception.

    Returns (message, errors). `Throttled` is special-cased so DRF's
    hardcoded "Expected available in X seconds." is replaced with a
    translated message based on the actual wait time.
    """
    # Rate limiting: translate DRF's default English throttling message.
    if isinstance(exc, Throttled):
        wait = getattr(exc, "wait", 0) or 0
        wait = math.ceil(wait)
        if wait > 60:
            minutes = max(1, wait // 60)
            msg = _("Too many requests. Please try again in %(minutes)d minute(s).")
            msg = msg % {"minutes": minutes}
        else:
            msg = _("Too many requests. Please try again in %(seconds)d second(s).")
            msg = msg % {"seconds": max(1, wait)}
        errors = {"detail": msg}
        return msg, errors

    # Special-case common DRF exceptions so messages follow Accept-Language
    # (DRF's built-in translations may be missing for `vi`/`kr`).
    from rest_framework.exceptions import (
        NotAuthenticated,
        PermissionDenied,
        MethodNotAllowed,
    )
    from django.http import Http404

    if isinstance(exc, NotAuthenticated):
        msg = _("Authentication credentials were not provided.")
        return msg, {"detail": msg}
    if isinstance(exc, PermissionDenied):
        msg = _("You do not have permission to perform this action")
        return msg, {"detail": msg}
    if isinstance(exc, Http404) or type(exc).__name__ == "NotFound":
        msg = _("Resource not found")
        return msg, {"detail": msg}
    if isinstance(exc, MethodNotAllowed):
        msg = _('Method "%(method)s" not allowed.') % {"method": exc.args[0] if exc.args else ""}
        return msg, {"detail": msg}

    if hasattr(exc, "detail"):
        if isinstance(exc.detail, dict):
            # Translated generic message instead of a raw dict repr.
            msg = _("Invalid data provided")
            return msg, exc.detail
        if isinstance(exc.detail, list):
            return str(exc.detail[0]) if exc.detail else str(exc), exc.detail
        return str(exc.detail), exc.detail
    return str(exc), (response.data if response else None)


class ServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = _("Service temporarily unavailable, try again later.")
    default_code = "service_unavailable"


class ValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("Invalid data provided.")
    default_code = "validation_error"


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = _("Resource conflict.")
    default_code = "conflict"


class ForbiddenError(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = _("You do not have permission to perform this action")
    default_code = "forbidden"


class NotFoundError(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = _("Resource not found.")
    default_code = "not_found"


class AuthRefreshError(APIException):
    """Lỗi của luồng refresh token — luôn trả **401**, không phải 400.

    VÌ SAO KHÔNG DÙNG `serializers.ValidationError` (400):
    Spec §23 yêu cầu 401 cho "refresh token invalid / revoked / expired /
    reuse detected". Nếu để 400 thì client không phân biệt được "sai dữ liệu
    gửi lên" với "phiên đã chết" ⇒ dễ xử lý sai (ví dụ coi là lỗi mạng rồi
    retry vô ích).

    `detail` là dict `{"code": ..., "detail": ...}` để `custom_exception_handler`
    trả nguyên vào `errors`, FE đọc `errors.code` thay vì đoán câu chữ.
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = _("Refresh token is not valid.")
    default_code = "auth_refresh_token_invalid"
