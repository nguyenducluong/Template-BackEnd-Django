"""
Tools hệ thống: health check (DB, Redis, Ollama).
"""
from __future__ import annotations

from .base import ToolSpec


def _system_health(user, args: dict) -> dict:
    from django.db import connection

    db = True
    try:
        connection.ensure_connection()
    except Exception:
        db = False

    redis = True
    try:
        from django.core.cache import cache

        cache.set("mcp:health", "ok", 5)
        redis = cache.get("mcp:health") == "ok"
    except Exception:
        redis = False

    return {"database": "ok" if db else "down", "redis": "ok" if redis else "down"}


system_health_tool = ToolSpec(
    name="system.health",
    description="Kiểm tra trạng thái Database và Redis.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_system_health,
)