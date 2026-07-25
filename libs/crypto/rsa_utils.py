"""
RSA-OAEP + AES-256-GCM utilities for API payload encryption.

Server keypair (generated via openssl, see started/docs/01_encryption_guide.md):
    certs/private_key.pem  — used to unwrap... (server side)
    certs/public_key.pem   — distributed to clients (not used for responses
                             in the mutual-handshake scheme)

Wire format (both directions):
    {"payload": "<base64 AES-GCM ciphertext>", "nonce": "<base64>"}
AES session keys are exchanged RSA-OAEP-wrapped during the handshake.
"""

import base64
import functools
import os
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from django.conf import settings


class CryptoError(Exception):
    """Raised when encryption/decryption fails (invalid payload, bad key...)."""


# ---------------------------------------------------------------------------
# Key loading (cached)
# ---------------------------------------------------------------------------

def _read_pem(path):
    full = Path(path)
    if not full.is_absolute():
        full = Path(settings.BASE_DIR) / path
    if not full.exists():
        raise CryptoError(f"Key file not found: {full}")
    return full.read_bytes()


@functools.lru_cache(maxsize=2)
def _load_public_key(path):
    """Load and cache a PEM RSA public key (server or client)."""
    try:
        return serialization.load_pem_public_key(_read_pem(path))
    except (ValueError, TypeError) as exc:
        raise CryptoError(f"Invalid public key: {exc}") from exc


@functools.lru_cache(maxsize=2)
def _load_private_key(path):
    """Load and cache a PEM RSA private key (unencrypted)."""
    try:
        return serialization.load_pem_private_key(_read_pem(path), password=None)
    except (ValueError, TypeError) as exc:
        raise CryptoError(f"Invalid private key: {exc}") from exc


def get_server_private_key():
    return _load_private_key(settings.RSA_PRIVATE_KEY_PATH)


def get_server_public_key():
    return _load_public_key(settings.RSA_PUBLIC_KEY_PATH)


def load_client_public_key(pem):
    """Parse and validate a client RSA public key PEM (min 2048-bit)."""
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

    try:
        key = serialization.load_pem_public_key(pem.encode() if isinstance(pem, str) else pem)
    except (ValueError, TypeError) as exc:
        raise CryptoError("Invalid client public key") from exc

    if not isinstance(key, RSAPublicKey):
        raise CryptoError("Key is not an RSA public key")
    if key.key_size < 2048:
        raise CryptoError(f"Client RSA key too small ({key.key_size} bits, min 2048)")
    return key


def clear_key_cache():
    """Drop cached keys (used after key rotation)."""
    _load_public_key.cache_clear()
    _load_private_key.cache_clear()


# ---------------------------------------------------------------------------
# RSA-OAEP wrap / unwrap of AES session keys (256-bit)
# ---------------------------------------------------------------------------

_OAEP = asym_padding.OAEP(
    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


def rsa_wrap_key(public_key, aes_key: bytes) -> str:
    """Wrap an AES key with an RSA public key -> base64 string."""
    return base64.b64encode(public_key.encrypt(aes_key, _OAEP)).decode()


def rsa_unwrap_key(wrapped_b64: str) -> bytes:
    """Unwrap an AES key with the server private key."""
    try:
        raw = base64.b64decode(wrapped_b64)
        return get_server_private_key().decrypt(raw, _OAEP)
    except Exception as exc:
        raise CryptoError("Failed to unwrap key") from exc


# ---------------------------------------------------------------------------
# AES-256-GCM payload encrypt / decrypt
# ---------------------------------------------------------------------------

def generate_aes_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def encrypt_payload(aes_key: bytes, plaintext: bytes, nonce: bytes | None = None):
    """AES-256-GCM encrypt. Returns (payload_b64, nonce_b64)."""
    if nonce is None:
        nonce = os.urandom(12)
    ct = AESGCM(aes_key).encrypt(nonce, plaintext, None)
    return base64.b64encode(ct).decode(), base64.b64encode(nonce).decode()


def decrypt_payload(aes_key: bytes, payload_b64: str, nonce_b64: str) -> bytes:
    """AES-256-GCM decrypt. Raises CryptoError on tamper/bad input."""
    try:
        ct = base64.b64decode(payload_b64)
        nonce = base64.b64decode(nonce_b64)
        if len(nonce) != 12:
            raise ValueError("nonce must be 12 bytes")
        return AESGCM(aes_key).decrypt(nonce, ct, None)
    except Exception as exc:
        raise CryptoError("Invalid encrypted payload") from exc
