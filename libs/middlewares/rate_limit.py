"""
Global rate limiting middleware.

Layer 1 of two-layer rate limiting:
  - This middleware counts EVERY request by client IP via Redis and returns
    429 once the per-IP budget for the window is exhausted. It runs before DRF
    views, protecting even unauthenticated/static-ish endpoints and acting as
    an application-level flood guard (similar to Nginx limit_req but in Django).

Layer 2 (per-view scoped throttles) lives in libs/auth/throttling.py and gives
fine-grained per-user + per-scope limits inside DRF.

Redundant with Nginx rate limiting, but valuable when running behind a simpler
proxy or during development. Configured via settings:
  - RATE_LIMIT_GLOBAL_MAX   (default 600 requests / window)
  - RATE_LIMIT_GLOBAL_WINDOW (default 60 seconds)
  - RATE_LIMIT_EXCLUDED_PREFIXES (default: admin, health, static/media, docs)
"""

import time

from django.conf import settings
from django.core.cache import cache
from django.utils import translation
from django.utils.translation.trans_real import parse_accept_lang_header


class RateLimitMiddleware:
    """Apply a global per-IP request budget stored in Redis."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_requests = getattr(settings, "RATE_LIMIT_GLOBAL_MAX", 600)
        self.window = getattr(settings, "RATE_LIMIT_GLOBAL_WINDOW", 60)
        self.excluded = [
            p.lower()
            for p in getattr(
                settings,
                "RATE_LIMIT_EXCLUDED_PREFIXES",
                ["/admin", "/api/v1/health", "/static", "/media", "/docs", "/schema"],
            )
        ]
        self._enabled = getattr(settings, "ENABLE_GLOBAL_RATE_LIMIT", True)
        self._supported = {code for code, _ in settings.LANGUAGES}

    def __call__(self, request):
        if not self._enabled or self._is_excluded(request.path):
            return self.get_response(request)

        ident = self._get_ident(request)
        if not ident:
            return self.get_response(request)

        key = f"ratelimit:global:{ident}"
        now = time.time()

        history = cache.get(key, [])
        history = [t for t in history if now - t < self.window]

        if len(history) >= self.max_requests:
            wait = max(1, int(self.window - (now - history[0]))) if history else self.window

            # Activate the client's preferred language so the 429 message is
            # localized even though this middleware runs before LanguageMiddleware.
            lang = self._best_lang(request.headers.get("Accept-Language", ""))
            translation.activate(lang)

            from django.http import JsonResponse
            from django.utils.translation import gettext as _

            return JsonResponse(
                {
                    "success": False,
                    "data": None,
                    "message": _("Too many requests. Please try again later."),
                    "errors": {"detail": "rate_limited", "retry_after": wait},
                    "meta": {"status_code": 429, "retry_after": wait},
                },
                status=429,
            )

        history.append(now)
        cache.set(key, history, timeout=self.window)
        return self.get_response(request)

    def _best_lang(self, header):
        """Pick the highest-priority supported language from an Accept-Language header."""
        for raw_code, _ in parse_accept_lang_header(header):
            candidates = {raw_code.lower(), raw_code.lower().split("-")[0]}
            for candidate in candidates:
                if candidate in self._supported:
                    return candidate
        return settings.LANGUAGE_CODE

    def _is_excluded(self, path):
        path = path.lower()
        return any(path.startswith(p) for p in self.excluded)

    def _get_ident(self, request):
        """Extract a stable client identifier (IP, honoring proxies)."""
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")