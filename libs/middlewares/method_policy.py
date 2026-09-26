"""
HTTP method policy middleware — chặn PUT / PATCH / DELETE trên toàn bộ API.

Xem ``libs/http_policy.py`` cho lý do và policy đầy đủ. Middleware này được đặt
sớm trong ``MIDDLEWARE`` (ngay sau ``SecurityMiddleware``) để:

    - Chặn TRƯỚC khi request đi qua rate limit / giải mã body (không tốn CPU).
    - Trả về đúng envelope ``{success, data, message, errors, meta}`` như mọi
      lỗi khác của API ⇒ FE xử lý lỗi đồng nhất, không phải parse HTML 405 của
      Django.
    - Kèm header ``Allow`` để client/proxy biết method hợp lệ.

Request không thuộc ``/api/`` (admin, docs, static, media, web socket) đi thẳng
qua để không phá hành vi mặc định của Django/DRF.
"""

from django.conf import settings
from django.http import JsonResponse
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation.trans_real import parse_accept_lang_header

from libs.http_policy import ALLOWED_METHODS_HEADER, is_method_allowed, is_protected_path


class MethodPolicyMiddleware:
    """Trả 405 (envelope chuẩn) cho PUT/PATCH/DELETE trên path API."""

    def __init__(self, get_response):
        self.get_response = get_response
        self._enabled = getattr(settings, "ENFORCE_HTTP_METHOD_POLICY", True)
        self._supported = {code for code, _ in settings.LANGUAGES}

    def __call__(self, request):
        if not self._enabled or is_method_allowed(request.method) or not is_protected_path(request.path):
            return self.get_response(request)

        # Kích hoạt ngôn ngữ của client để message 405 được dịch (middleware này
        # chạy TRƯỚC LanguageMiddleware nên phải tự activate).
        translation.activate(self._best_lang(request.headers.get("Accept-Language", "")))
        message = _('Method "%(method)s" not allowed. Use POST instead.') % {"method": request.method}

        response = JsonResponse(
            {
                "success": False,
                "data": None,
                "message": message,
                "errors": {"detail": message, "allowed_methods": ALLOWED_METHODS_HEADER.split(", ")},
                "meta": {"status_code": 405},
            },
            status=405,
        )
        response["Allow"] = ALLOWED_METHODS_HEADER
        response["Content-Language"] = translation.get_language()
        return response

    def _best_lang(self, header):
        """Chọn ngôn ngữ ưu tiên cao nhất mà server hỗ trợ (giống LanguageMiddleware)."""
        for raw_code, _q in parse_accept_lang_header(header):
            normalized = raw_code.lower()
            for candidate in ("ko" if normalized in ("ko", "ko-kr") else normalized, normalized, normalized.split("-")[0]):
                if candidate and candidate in self._supported:
                    return candidate
        return settings.LANGUAGE_CODE
