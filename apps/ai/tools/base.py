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
        # list định danh power cần thiết — int/chuỗi số = SystemPower.id,
        # chuỗi khác = SystemPower.power_en (exact) — theo _0039/_0040.
        self.required_powers = required_powers or []

    def call(self, user, args: Dict[str, Any]):
        """Chạy tool: kiểm tra quyền trước, gọi handler sau.

        Mọi exception (kể cả exception của kiểm tra quyền) đều được bọc lại
        -> trả về error content thay vì để lộ 500/stacktrace (S3).
        """
        try:
            if self.required_powers and not has_power(user, self.required_powers):
                return {
                    "isError": True,
                    "content": [{
                        "type": "text",
                        "text": "Bạn không có quyền thực hiện thao tác này.",
                    }],
                }
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


def has_power(user, required_powers: List[Union[str, int]]) -> bool:
    """Kiểm tra user có bất kỳ power nào trong required_powers (đã approved).

    Nguồn quyền (bảng `_0039 SystemPermission` + `_0040
    UserSystemPermissionRegistration`):

    - Quyền cấp org: chỉ tính khi ``type=NO_REGISTRATION`` (không cần đăng ký)
      và ``status=APPROVED`` — quyền ``NEED_REGISTRATION`` phải có đăng ký
      từng user ở nhánh (2).
    - Quyền cấp user: ``UserSystemPermissionRegistration.status=APPROVED`` và
      permission cha (``system_permission``) cũng phải ``APPROVED``.

    Định danh power:
    - int / chuỗi số → ``SystemPower.id`` (chuẩn P1.6);
    - chuỗi khác     → ``SystemPower.power_en`` (exact match, P1.5).

    Mọi lỗi truy vấn được nuốt → False (fail-closed, không để FieldError/Lỗi
    DB làm 500 cho tool).
    """
    if not user or not getattr(user, "id", None) or not required_powers:
        return False

    # Tách required_powers thành (id cần match, tên cần match)
    power_ids: set = set()
    power_names: set = set()
    for power in required_powers:
        try:
            power_ids.add(int(power))
        except (TypeError, ValueError):
            power_names.add(str(power))
    if not power_ids and not power_names:
        return False

    from apps.info.models import SystemPermission, UserSystemPermissionRegistration

    try:
        # (1) Quyền công khai cấp org — chỉ NO_REGISTRATION mới tự áp dụng
        org_grants = set(
            SystemPermission.objects.filter(
                org_id=getattr(user, "org_id", None),
                type=SystemPermission.TypeChoices.NO_REGISTRATION,
                status=SystemPermission.StatusChoices.APPROVED,
            ).values_list("power_id", "power__power_en")
        )
        # (2) Quyền user đã được duyệt — permission cha cũng phải APPROVED
        user_grants = set(
            UserSystemPermissionRegistration.objects.filter(
                registered_by_id=user.id,
                status=UserSystemPermissionRegistration.StatusChoices.APPROVED,
                system_permission__status=SystemPermission.StatusChoices.APPROVED,
            ).values_list("system_permission__power_id", "system_permission__power__power_en")
        )
    except Exception:  # noqa: BLE001 — không để lỗi query làm tool 500
        logger.exception("has_power: lỗi tra cứu quyền của user %s", user.id)
        return False

    granted_ids = {g[0] for g in org_grants | user_grants}
    granted_names = {g[1] for g in org_grants | user_grants}
    if power_ids & granted_ids:
        return True
    return bool(power_names & granted_names)