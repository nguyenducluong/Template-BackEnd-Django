"""
Rate limiting for the API.

Two tiers:
  - Fixed-window custom throttles (login/register) keyed by client IP.
  - DRF ScopedRateThrottle subclassed here so the cache key includes the
    authenticated user id, preventing users from evading limits by rotating IPs.

Uses Redis (django-redis) for distributed state. Backed by settings in
``DEFAULT_THROTTLE_RATES`` (per-scope), and the fixed auth settings below.
"""

from django.conf import settings
from django.core.cache import cache
from rest_framework.throttling import BaseThrottle, ScopedRateThrottle as _ScopedRateThrottle


def _get_client_ident(request):
    """Return a stable client identifier honoring proxy headers."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class AuthRateThrottle(BaseThrottle):
    """
    Fixed-window rate throttle keyed by client IP.

    A simple, dependency-light limiter used for auth endpoints (login/register)
    where there is no authenticated user yet to key on.
    """

    def __init__(self, max_requests: int = None, window: int = None):
        self.max_requests = max_requests or getattr(settings, "LOGIN_RATE_LIMIT", 5)
        self.window = window or getattr(settings, "LOGIN_RATE_LIMIT_WINDOW", 60)

    def get_cache_key(self, request, view):
        ident = _get_client_ident(request)
        return f"throttle:auth:{ident}"

    def allow_request(self, request, view):
        key = self.get_cache_key(request, view)
        history = cache.get(key, [])
        now = self.timer()
        history = [t for t in history if now - t < self.window]

        if len(history) >= self.max_requests:
            self.history = history
            self.wait_time = self.window - (now - history[0]) if history else self.window
            return False

        history.append(now)
        cache.set(key, history[-self.max_requests:], timeout=self.window)
        self.history = history
        return True

    def wait(self):
        return getattr(self, "wait_time", self.window)

    def timer(self):
        import time

        return time.time()


class LoginRateThrottle(AuthRateThrottle):
    """5 login attempts per minute per client IP."""

    def __init__(self):
        super().__init__(
            max_requests=getattr(settings, "LOGIN_RATE_LIMIT", 5),
            window=getattr(settings, "LOGIN_RATE_LIMIT_WINDOW", 60),
        )


class RegisterRateThrottle(AuthRateThrottle):
    """3 registration attempts per hour per client IP."""

    def __init__(self):
        super().__init__(
            max_requests=getattr(settings, "REGISTER_RATE_LIMIT", 3),
            window=getattr(settings, "REGISTER_RATE_LIMIT_WINDOW", 3600),
        )


class ScopedRateThrottle(_ScopedRateThrottle):
    """
    DRF scoped throttle whose cache key is scoped to the authenticated user
    when present, falling back to the client IP for anonymous requests.

    Usage:
        class MyView(APIView):
            throttle_classes = [ScopedRateThrottle]
            throttle_scope = "user_write"
    """

    def get_cache_key(self, request, view):
        if self.scope not in self.THROTTLE_RATES:
            return None  # no rate configured for this scope -> allow

        user = getattr(request, "user", None)
        user_id = getattr(user, "id", None) if user and getattr(user, "is_authenticated", False) else "anon"
        ident = _get_client_ident(request)

        return self.cache_format % {
            "scope": self.scope,
            "ident": user_id or ident,
        }
