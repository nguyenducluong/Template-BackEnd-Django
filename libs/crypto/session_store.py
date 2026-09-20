"""
Encrypted-session storage (muc 1 — session-only).

Handshake flow:
    1. Client POSTs its RSA public key (PEM) to /api/crypto/handshake
    2. Server generates an AES-256 session key, stores it in Redis and
       returns it RSA-OAEP-wrapped with the CLIENT's public key
    3. Both sides then encrypt/decrypt payloads with the session key

Storage: Django cache backend (Redis in staging/production, LocMem in dev).
"""

import base64
import uuid

from django.core.cache import cache

from libs.crypto.rsa_utils import encrypt_payload, generate_aes_key

PREFIX = "crypto:session"


def _key(session_id: str) -> str:
    return f"{PREFIX}:{session_id}"


def create_session(client_public_key_pem: str, ttl: int) -> dict:
    """
    Create a new encrypted session.

    Generates an AES-256 key, wraps it with the CLIENT's public key
    (RSA-OAEP), stores everything in Redis and returns the handshake
    response body:
        {"session_id", "key", "nonce", "payload", "expires_in"}
    where `payload`/`nonce` carry an integrity probe encrypted with the
    session key ('{"alg":"AES-256-GCM"}') that the client can verify
    after unwrapping `key` with its private key.
    """
    from libs.crypto.rsa_utils import load_client_public_key, rsa_wrap_key

    session_id = uuid.uuid4().hex
    aes_key = generate_aes_key()
    wrapped_key_b64 = rsa_wrap_key(load_client_public_key(client_public_key_pem), aes_key)
    cache.set(
        _key(session_id),
        {
            "aes_key": base64.b64encode(aes_key).decode(),
            "client_public_key": client_public_key_pem,
        },
        timeout=ttl,
    )
    payload_b64, nonce_b64 = encrypt_payload(aes_key, b'{"alg":"AES-256-GCM"}')
    return {
        "session_id": session_id,
        "key": wrapped_key_b64,  # AES key wrapped with the CLIENT public key
        "payload": payload_b64,
        "nonce": nonce_b64,
        "expires_in": ttl,
    }


def get_session(session_id: str, ttl: int | None = None) -> dict | None:
    """Return session data, sliding the TTL on each successful access."""
    session = cache.get(_key(session_id))
    if session is not None and ttl:
        cache.set(_key(session_id), session, timeout=ttl)
    return session


def get_session_aes_key(session_id: str, ttl: int | None = None) -> bytes | None:
    """Return the raw AES key of a session (None if expired/unknown)."""
    session = get_session(session_id, ttl)
    if session is None:
        return None
    return base64.b64decode(session["aes_key"])


def delete_session(session_id: str) -> None:
    cache.delete(_key(session_id))


def get_session_client_public_key(session_id: str, ttl: int | None = None) -> str | None:
    """Return the CLIENT RSA public key PEM of a session (None if expired/unknown).

    Dùng cho chiều RESPONSE: server wrap AES key mới của từng response bằng
    public key này, client unwrap bằng private key của chính nó.
    """
    session = get_session(session_id, ttl)
    if session is None:
        return None
    return session.get("client_public_key")
