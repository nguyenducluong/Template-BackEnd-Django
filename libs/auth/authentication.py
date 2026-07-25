"""
Custom DRF authentication class that validates JWT Bearer tokens.

Usage in ``settings.py``::

    REST_FRAMEWORK = {
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "libs.auth.authentication.JWTAuthentication",
        ],
    }
"""

import jwt
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

from libs.auth.jwt_utils import _resolve_user, decode_access_token


class JWTAuthentication(BaseAuthentication):
    """
    Authenticate the request using a Bearer JWT in the ``Authorization``
    header.

    On success, returns ``(user, token_payload)``.

    On a missing/malformed header, returns ``None`` so that DRF falls
    back to its own unauthenticated handling (``request.user`` becomes
    ``AnonymousUser`` and ``request.successful_authenticator`` stays
    ``None``, which yields ``401 Unauthorized`` for ``IsAuthenticated``).

    On an invalid or expired token, raises ``AuthenticationFailed``.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "").strip()
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None

        token = parts[1]
        try:
            payload = decode_access_token(token)
            user = _resolve_user(payload)
            return (user, payload)
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed("Token has expired")
        except jwt.InvalidTokenError as exc:
            raise exceptions.AuthenticationFailed(f"Invalid token: {exc}")

    def authenticate_header(self, request) -> str:
        return self.keyword
