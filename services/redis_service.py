"""
Redis service for caching, pub/sub, rate limiting, and distributed locks.
"""
import json
import logging
from typing import Any, Optional

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class RedisService:
    """
    Service for Redis operations.
    Provides caching, pub/sub, rate limiting, and distributed locking.
    """

    # ---- Cache Operations ----

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """Get value from cache."""
        value = cache.get(key)
        return value if value is not None else default

    @staticmethod
    def set(key: str, value: Any, timeout: int = 300) -> bool:
        """Set value in cache with timeout (seconds)."""
        return cache.set(key, value, timeout=timeout)

    @staticmethod
    def delete(key: str) -> bool:
        """Delete key from cache."""
        return cache.delete(key)

    @staticmethod
    def set_many(data: dict, timeout: int = 300) -> bool:
        """Set multiple key-value pairs."""
        cache.set_many(data, timeout=timeout)

    @staticmethod
    def get_many(keys: list) -> dict:
        """Get multiple values by keys."""
        return cache.get_many(keys)

    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """Delete all keys matching pattern (uses SCAN, never blocking KEYS).

        ``KEYS`` is O(N) over the whole keyspace and blocks the Redis server;
        ``scan_iter`` walks the keyspace incrementally instead.
        """
        from django_redis import get_redis_connection

        conn = get_redis_connection("default")
        deleted = 0
        batch = []
        for key in conn.scan_iter(match=pattern, count=500):
            batch.append(key)
            if len(batch) >= 500:
                deleted += conn.delete(*batch)
                batch = []
        if batch:
            deleted += conn.delete(*batch)
        return deleted

    # ---- OTP (Forgot / Reset Password) ----

    @staticmethod
    def store_otp(identifier: str, otp: str, ttl: int = 300) -> bool:
        """Store an OTP in Redis keyed by *identifier* (knox_id or email)."""
        key = f"otp:{identifier}"
        return RedisService.set(key, otp, timeout=ttl)

    @staticmethod
    def verify_otp(identifier: str, otp: str, max_attempts: int | None = None) -> bool:
        """Verify OTP matches the stored value.

        Brute-force protection (uses settings.OTP_MAX_ATTEMPTS, default 3):
        - Each failed attempt increments a per-identifier attempt counter
          (same TTL as the OTP itself).
        - When the counter reaches *max_attempts* the OTP is deleted, so
          further guesses can never succeed even within the OTP TTL window.

        Returns True on success; on success the attempt counter is cleared.
        """
        from django.conf import settings

        key = f"otp:{identifier}"
        attempts_key = f"otp_attempts:{identifier}"

        stored = RedisService.get(key)
        if stored is None:
            return False

        if str(stored) != str(otp):
            max_attempts = max_attempts or getattr(settings, "OTP_MAX_ATTEMPTS", 3)
            attempts = (cache.get(attempts_key, 0) or 0) + 1
            if attempts >= max_attempts:
                # Too many wrong guesses — invalidate the OTP entirely.
                cache.delete(key)
                cache.delete(attempts_key)
            else:
                cache.set(attempts_key, attempts, timeout=getattr(settings, "OTP_EXPIRY_SECONDS", 300))
            return False

        cache.delete(attempts_key)
        return True

    @staticmethod
    def delete_otp(identifier: str) -> bool:
        """Delete a stored OTP and its attempt counter."""
        key = f"otp:{identifier}"
        cache.delete(f"otp_attempts:{identifier}")
        return RedisService.delete(key)

    @staticmethod
    def store_reset_token(knox_id: str, token: str, ttl: int = 600) -> bool:
        """Store a password-reset token linked to a knox_id."""
        key = f"reset:{knox_id}"
        return RedisService.set(key, token, timeout=ttl)

    @staticmethod
    def verify_reset_token(knox_id: str, token: str) -> bool:
        """Verify a password-reset token."""
        key = f"reset:{knox_id}"
        stored = RedisService.get(key)
        if stored is None:
            return False
        return str(stored) == str(token)

    @staticmethod
    def delete_reset_token(knox_id: str) -> bool:
        """Delete a stored reset token."""
        key = f"reset:{knox_id}"
        return RedisService.delete(key)

    # ---- Rate Limiting ----

    @staticmethod
    def check_rate_limit(key: str, max_requests: int, window: int) -> bool:
        """
        Check if request is within rate limit.
        Returns True if allowed, False if rate limited.
        """
        import time
        from django_redis import get_redis_connection

        conn = get_redis_connection("default")
        now = int(time.time())
        window_key = f"ratelimit:{key}:{now // window}"

        current = conn.get(window_key)
        if current is None:
            conn.setex(window_key, window, 1)
            return True
        elif int(current) < max_requests:
            conn.incr(window_key)
            return True
        return False

    # ---- Distributed Lock ----

    @staticmethod
    def acquire_lock(lock_key: str, timeout: int = 10) -> bool:
        """Acquire a distributed lock (atomic: SET NX + EX in one command).

        Previously used setnx() then expire() as two separate calls — if the
        process crashed in between, the lock leaked forever. ``SET ... NX EX``
        is atomic so the lock always carries an expiry.
        """
        from django_redis import get_redis_connection

        conn = get_redis_connection("default")
        # set(..., nx=True, ex=...) returns True only when the key was set.
        return bool(conn.set(f"lock:{lock_key}", "locked", nx=True, ex=timeout))

    @staticmethod
    def release_lock(lock_key: str) -> None:
        """Release a distributed lock."""
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        conn.delete(f"lock:{lock_key}")

    # ---- Pub/Sub ----

    @staticmethod
    def publish(channel: str, message: dict) -> None:
        """Publish a message to a channel."""
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        conn.publish(channel, json.dumps(message))
        logger.info(f"Published message to channel: {channel}")