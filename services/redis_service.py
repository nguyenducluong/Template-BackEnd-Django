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
        """Delete all keys matching pattern."""
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        keys = conn.keys(pattern)
        if keys:
            return conn.delete(*keys)
        return 0

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
        """Acquire a distributed lock."""
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        return conn.setnx(f"lock:{lock_key}", "locked") and conn.expire(f"lock:{lock_key}", timeout)

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