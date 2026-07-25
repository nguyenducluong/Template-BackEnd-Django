"""
Custom authentication package.

Provides JWT-based authentication without depending on django.contrib.auth:
- Password hashing / verification (PBKDF2-SHA256)
- JWT token generation, verification, and blacklisting
- DRF authentication class
- WebSocket JWT middleware
- Custom AnonymousUser
"""

from libs.auth.password import make_password, check_password
from libs.auth.jwt_utils import (
    generate_access_token,
    generate_refresh_token,
    generate_tokens,
    verify_access_token,
    verify_refresh_token,
    blacklist_token,
    is_token_blacklisted,
    decode_access_token,
)
from libs.auth.authentication import JWTAuthentication

__all__ = [
    "make_password",
    "check_password",
    "generate_access_token",
    "generate_refresh_token",
    "generate_tokens",
    "verify_access_token",
    "verify_refresh_token",
    "blacklist_token",
    "is_token_blacklisted",
    "decode_access_token",
    "JWTAuthentication",
]