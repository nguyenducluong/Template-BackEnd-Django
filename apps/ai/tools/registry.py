"""
Tool registry — nơi đăng ký tập trung mọi tool AI trong hệ thống.

Thêm tool mới: viết 1 hàm trong apps/ai/tools/<domain>_tools.py, rồi thêm
1 ToolSpec vào TOOLS dưới đây (hoặc import từ module).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import ToolSpec
from .face_tools import face_search_tool
from .info_tools import header_structure_tool, org_tree_tool, orgs_tool
from .system_tools import system_health_tool
from .user_tools import user_by_gen_id_tool, user_by_id_tool

TOOLS: Dict[str, ToolSpec] = {t.name: t for t in [
    header_structure_tool,
    orgs_tool,
    org_tree_tool,
    user_by_id_tool,
    user_by_gen_id_tool,
    face_search_tool,
    system_health_tool,
]}

# First-party tools chỉ "đọc" (chưa có write) — dùng để quyết định JSON fallback
ALLOWED_TOOL_NAMES = set(TOOLS)


def list_tools_schemas() -> list:
    """Toàn bộ tool schema (JSON Schema) — cho native tool-calling."""
    return [t.to_ollama_tool() for t in TOOLS.values()]


def execute_tool(name: str, user, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Dispatch tool theo name. Trả về dict MCP-style."""
    spec = TOOLS.get(name)
    if spec is None:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"Tool '{name}' không tồn tại."}],
        }
    return spec.call(user, args or {})