"""
ToolSpec — chuẩn tool contract theo MCP (name/description/inputSchema/handler).

Mỗi tool = một "khả năng" AI trong Django gọi được để đọc/phân tích dữ liệu
hệ thống. input_schema theo JSON Schema (tương thích MCP tools/OpenAI tools)
để dùng được với cả native tool-calling lẫn JSON fallback.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger("apps")

Handler = Callable[[Any, Dict[str, Any]], Any]

# Kết quả tool — dict chuẩn được normalize về MCP content ["text", ...]
ToolResult = Union[str, Dict[str, Any], List[Any]]


class ToolSpec:
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Handler,
        required_powers: Optional[List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler
        # list power code (SystemPower.code) cần thiết — theo _0039/_0040.
        self.required_powers = required_powers or []

    def call(self, user, args: Dict[str, Any]):
        """Chạy tool: kiểm tra quyền trước, gọi handler sau.

        Mọi exception của handler được bọc lại -> trả về error content thay vì
        để lộ 500/stacktrace (S3).
        """
        if self.required_powers and not has_power(user, self.required_powers):
            return {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": "Bạn không có quyền thực hiện thao tác này.",
                }],
            }
        try:
            return self.handler(user, args or {})
        except Exception as exc:  # noqa: BLE001 - chặn mọi lỗi tool
            logger.exception("Tool %s failed", self.name)
            return {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": f"Tool '{self.name}' gặp lỗi: {exc}",
                }],
            }

    # ---- schema dùng cho native tool-calling (OpenAI/Ollama format) ----
    def to_ollama_tool(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


def has_power(user, required_powers: List[str]) -> bool:
    """Kiểm tra user có bất kỳ power nào trong required_powers (approved).

    Tái dùng bảng `_0039 SystemPermission` (org) + `_0040
    UserSystemPermissionRegistration` (user) — đều cần status APPROVED.
    """
    if not user or not getattr(user, "id", None):
        return False

    from apps.info.models import SystemPermission, UserSystemPermissionRegistration

    approved = set(
        SystemPermission.objects.filter(
            org_id=user.org_id, status=SystemPermission.StatusChoices.APPROVED
        ).values_list("power__code", flat=True)
    )
    approved |= set(
        UserSystemPermissionRegistration.objects.filter(
            registered_by_id=user.id,
            status=UserSystemPermissionRegistration.StatusChoices.APPROVED,
        ).values_list("system_permission__power__code", flat=True)
    )
    return any(p in approved for p in required_powers)