"""
Custom password hashing utilities using PBKDF2-SHA256.

No dependency on django.contrib.auth.hashers.
The hash format mirrors Django's ``pbkdf2_sha256`` scheme so that
passwords remain portable if Django auth is ever reintroduced:

    pbkdf2_sha256$<iterations>$<salt>$<hash_hex>
"""

import hashlib
import hmac
import secrets

# OWASP-recommended minimum iterations (as of 2023)
DEFAULT_ITERATIONS = 600_000
HASH_ALGORITHM = "sha256"
SALT_BYTES = 16
HASH_BYTES = 32
MAX_PASSWORD_BYTES = 1024


def make_password(password: str, iterations: int = DEFAULT_ITERATIONS) -> str:
    """
    Hash *password* using PBKDF2-SHA256 and return a string suitable
    for storage in a ``CharField``.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Password is too long")

    salt = secrets.token_bytes(SALT_BYTES).hex()
    hash_val = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
        dklen=HASH_BYTES,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${hash_val}"


def check_password(password: str, encrypted: str) -> bool:
    """
    Verify *password* against the stored *encrypted* hash.

    Returns ``False`` for empty/unrecognised hashes instead of raising,
    matching the semantics of Django's ``check_password``.
    """
    if not encrypted or not encrypted.startswith("pbkdf2_sha256$"):
        return False

    parts = encrypted.split("$")
    if len(parts) != 4:
        return False

    _, iterations_str, salt, stored_hash = parts
    try:
        iterations = int(iterations_str)
    except (ValueError, TypeError):
        return False

    new_hash = hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
        dklen=HASH_BYTES,
    ).hex()

    return hmac.compare_digest(new_hash, stored_hash)


def needs_rehash(encrypted: str, iterations: int = DEFAULT_ITERATIONS) -> bool:
    """
    Return ``True`` if the *encrypted* hash uses fewer iterations than
    *iterations* (i.e. it should be re-hashed).
    """
    if not encrypted or not encrypted.startswith("pbkdf2_sha256$"):
        return True
    parts = encrypted.split("$")
    if len(parts) != 4:
        return True
    try:
        return int(parts[1]) < iterations
    except (ValueError, TypeError):
        return True
