"""
WebSocket JWT middleware for Django Channels.

Replaces ``channels.auth.AuthMiddlewareStack``.

Tokens are expected in one of three places:
1. ``Authorization: Bearer <token>`` header (standard)
2. ``?token=<token>`` query-string parameter (for WebSocket clients
   that cannot set custom headers before the handshake)
3. ``jwt`` cookie

If a valid access token is found, ``scope["user"]`` is set to the
corresponding ``User``; otherwise it is set to ``AnonymousUser``.
"""

import logging
from typing import Any, Dict
from urllib.parse import parse_qs

from channels.db import database_sync_to_async

from libs.auth.anonymous_user import AnonymousUser
from libs.auth.jwt_utils import _resolve_user, decode_access_token

logger = logging.getLogger(__name__)


class JWTAuthMiddleware:
    """ASGI middleware that populates ``scope["user"]`` from a JWT."""

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope: Dict[str, Any], receive, send):
        if "user" not in scope:
            token = self._extract_token(scope)
            # The user lookup hits the database, so it must run in a
            # sync thread to avoid SynchronousOnlyOperation inside the
            # event loop.
            scope["user"] = await database_sync_to_async(self._authenticate)(token)
        await self.inner(scope, receive, send)

    # ------------------------------------------------------------------
    # Token extraction
    # ------------------------------------------------------------------

    def _extract_token(self, scope: Dict[str, Any]) -> str:
        """Try headers → query string → cookies, return token or empty str."""
        # 1. Authorization header
        headers = dict(scope.get("headers", []))
        raw_auth = headers.get(b"authorization", b"")
        auth_str = raw_auth.decode("utf-8", errors="ignore").strip()
        if auth_str:
            parts = auth_str.split()
            if len(parts) == 2 and parts[0] == "Bearer":
                return parts[1]

        # 2. Query string
        query_string = scope.get("query_string", b"")
        if isinstance(query_string, bytes):
            query_string = query_string.decode("utf-8", errors="ignore")
        params = parse_qs(query_string)
        token_vals = params.get("token", [])
        if token_vals:
            return token_vals[0]

        # 3. Cookie
        cookies = headers.get(b"cookie", b"")
        cookie_str = cookies.decode("utf-8", errors="ignore")
        for pair in cookie_str.split(";"):
            pair = pair.strip()
            if "=" in pair:
                name, value = pair.split("=", 1)
                if name.strip() == "jwt":
                    return value.strip()

        return ""

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _authenticate(self, token: str):
        """Return the ``User`` for *token*, or ``AnonymousUser``."""
        if not token:
            return AnonymousUser()
        try:
            payload = decode_access_token(token)
            return _resolve_user(payload)
        except Exception:
            # Invalid/expired token or DB error — fail closed as anonymous.
            logger.debug("WebSocket JWT authentication failed", exc_info=True)
            return AnonymousUser()


def JWTAuthMiddlewareStack(inner):
    """Convenience wrapper — use in ``config/asgi.py``."""
    return JWTAuthMiddleware(inner)
