"""
Custom JWT utilities built on top of PyJWT.

Replaces ``djangorestframework_simplejwt`` entirely.

Token payload structure
-----------------------
::

    {
        "token_type": "access" | "refresh",
        "jti":         "<uuid>",
        "user_id":     "<id>",
        "user_gen_id": "<8-digit gen_id>",
        "iat":         <epoch>,
        "exp":         <epoch>,
    }
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from django.conf import settings
from django.core.cache import cache

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------

def _get_config() -> Dict[str, Any]:
    """Return merged JWT configuration from Django settings."""
    jwt_settings = getattr(settings, "JWT_AUTH", {})
    return {
        "ACCESS_TOKEN_LIFETIME": jwt_settings.get(
            "ACCESS_TOKEN_LIFETIME", timedelta(minutes=15),
        ),
        "REFRESH_TOKEN_LIFETIME": jwt_settings.get(
            "REFRESH_TOKEN_LIFETIME", timedelta(days=7),
        ),
        "ALGORITHM": jwt_settings.get("ALGORITHM", "HS256"),
        "SIGNING_KEY": jwt_settings.get("SIGNING_KEY", settings.SECRET_KEY),
        "USER_ID_CLAIM": jwt_settings.get("USER_ID_CLAIM", "user_id"),
        "AUTH_HEADER_TYPES": jwt_settings.get("AUTH_HEADER_TYPES", ("Bearer",)),
    }


def _generate_jti() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

def _build_payload(user, token_type: str, lifetime: timedelta) -> Dict[str, Any]:
    """Build the JWT payload for *user* and *token_type*."""
    now = datetime.now(tz=timezone.utc)
    return {
        "token_type": token_type,
        "jti": _generate_jti(),
        "user_id": str(user.id),
        "user_gen_id": user.gen_id,
        "iat": now,
        "exp": now + lifetime,
    }


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

def generate_access_token(user) -> str:
    """Create a signed access-token string for *user*."""
    cfg = _get_config()
    payload = _build_payload(user, "access", cfg["ACCESS_TOKEN_LIFETIME"])
    return jwt.encode(payload, cfg["SIGNING_KEY"], algorithm=cfg["ALGORITHM"])


def generate_refresh_token(user) -> str:
    """Create a signed refresh-token string for *user*."""
    cfg = _get_config()
    payload = _build_payload(user, "refresh", cfg["REFRESH_TOKEN_LIFETIME"])
    return jwt.encode(payload, cfg["SIGNING_KEY"], algorithm=cfg["ALGORITHM"])


def generate_tokens(user) -> Dict[str, str]:
    """Return ``{"access": ..., "refresh": ...}`` for *user*."""
    return {
        "access": generate_access_token(user),
        "refresh": generate_refresh_token(user),
    }


# ---------------------------------------------------------------------------
# Internal decode helper
# ---------------------------------------------------------------------------

def _decode(token: str) -> Dict[str, Any]:
    """Decode *token* and return its payload (raises on failure)."""
    cfg = _get_config()
    return jwt.decode(
        token,
        cfg["SIGNING_KEY"],
        algorithms=[cfg["ALGORITHM"]],
        options={"require": ["exp", "iat", "token_type", "user_id"]},
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode *token* and return its payload, raising ``jwt.PyJWTError``
    if the token is invalid, expired, or not an access token.

    Shared by the DRF authentication class and the WebSocket middleware
    so the decoding rules live in exactly one place.
    """
    payload = _decode(token)
    if payload.get("token_type") != "access":
        raise jwt.InvalidTokenError("Expected access token type")
    return payload


def _resolve_user(payload: Dict[str, Any]):
    """Look up the user referenced by *payload* (raises if not found)."""
    from apps.accounts.models import User  # local import — avoid circular deps

    user_id = payload.get("user_id")
    if not user_id:
        raise jwt.InvalidTokenError("Token payload missing user_id claim")
    try:
        user = User.objects.select_related("org", "shift").get(id=user_id)
    except User.DoesNotExist:
        raise jwt.InvalidTokenError("User not found")
    return user


# ---------------------------------------------------------------------------
# Token verification (public API)
# ---------------------------------------------------------------------------

def verify_access_token(token: str):
    """Validate an access token and return the ``User``."""
    payload = _decode(token)
    if payload.get("token_type") != "access":
        raise jwt.InvalidTokenError("Expected access token type")
    return _resolve_user(payload)


def verify_refresh_token(token: str):
    """Validate a refresh token and return the ``User``."""
    payload = _decode(token)
    if payload.get("token_type") != "refresh":
        raise jwt.InvalidTokenError("Expected refresh token type")

    jti = payload.get("jti")
    if jti and is_token_blacklisted(jti):
        raise jwt.InvalidTokenError("Token has been blacklisted")

    return _resolve_user(payload)


# ---------------------------------------------------------------------------
# Token blacklisting (DB-backed with cache fast-path)
# ---------------------------------------------------------------------------

def _blacklist_key(jti: str) -> str:
    return f"jwt:blacklist:{jti}"


def blacklist_token(token: str) -> None:
    """Blacklist *token* until it expires (Phase 1b: DB + cache)."""
    try:
        payload = _decode(token)
    except jwt.PyJWTError:
        return

    jti = payload["jti"]
    exp = payload["exp"]
    now = datetime.now(tz=timezone.utc).timestamp()
    ttl = max(int(exp - now), 0)

    # Phase 1b: Persist to DB (source of truth)
    from apps.accounts.models import JWTBlacklist
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
    JWTBlacklist.objects.get_or_create(jti=jti, defaults={"expires_at": expires_at})

    # Cache as fast-path (survives restarts via DB). Guard: a timeout of 0
    # means "never expire" in Django's cache API, and the token may already
    # be at (or past) expiry — clamp to a small positive value.
    cache.set(_blacklist_key(jti), True, timeout=max(ttl, 60))


def is_token_blacklisted(jti: str) -> bool:
    """Return ``True`` if *jti* has been blacklisted (Phase 1b: cache then DB)."""
    # Fast-path: check cache first
    if cache.get(_blacklist_key(jti)):
        return True

    # Phase 1b: Check DB (source of truth)
    from apps.accounts.models import JWTBlacklist
    if JWTBlacklist.objects.filter(jti=jti).exists():
        # Refresh cache for subsequent checks
        cache.set(_blacklist_key(jti), True, timeout=3600)
        return True
    return False


def rotate_refresh_token(old_refresh_token: str):
    """Verify *old_refresh_token*, blacklist it, issue a new pair."""
    user = verify_refresh_token(old_refresh_token)
    blacklist_token(old_refresh_token)
    tokens = generate_tokens(user)
    return tokens["access"], tokens["refresh"], user