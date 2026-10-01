"""
ToolSpec — chuẩn tool contract theo MCP (name/description/inputSchema/handler).

Mỗi tool = một "khả năng" AI trong Django gọi được để đọc/phân tích dữ liệu
hệ thống. input_schema theo JSON Schema (tương thích MCP tools/OpenAI tools)
để dùng được với cả native tool-calling lẫn JSON fallback.

BA LỚP PHÒNG AN TOÀN (không được bỏ bớt):
  1. ``required_powers``  — user phải có quyền (SystemPermission).
  2. ``required_headers`` — user phải có quyền truy cập header (HeaderRegistration).
  3. ``validate_args``    — args phải khớp JSON Schema trước khi vào handler.
Cả ba đều chạy ở SERVER. Ẩn nút trong UI không phải bảo vệ.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger("apps")

Handler = Callable[[Any, Dict[str, Any]], Any]

# Kết quả tool — dict chuẩn được normalize về MCP content ["text", ...]
ToolResult = Union[str, Dict[str, Any], List[Any]]

# Nội dung 1 cho mọi tool: trả nhiệm tool ngay cả khi handler ném lỗi vô hại thành cách.
DENIED_TEXT = "Bạn không có quyền thực hiện thao tác này."


def _error_result(message: str) -> Dict[str, Any]:
    """Dựng MCP error content — dùng chung để không lặp chuỗi dict 4 nơi."""
    return {"isError": True, "content": [{"type": "text", "text": message}]}


# --- Dịch thông báo của jsonschema sang tiếng Việt ----------------------------
# jsonschema trả message tiếng Anh ("'a' is a required property"). Message này
# chạy thẳng ra cho user/AI, để tiếng Anh sẽ rất khó đọc và khi model sửa lại
# tham số cũng bị lệch. Dùng regex + có fallback nên an toàn: không khớp
# được pattern nào thì trả nguyên message gốc.
_MSG_RULES = (
	(re.compile(r"^'(?P<k>[^']+)' is a required property$"), lambda m: "thiếu tham số bắt buộc '%s'" % m.group("k")),
	(re.compile(r"^'(?P<v>.*)' is not one of \\[(?P<opts>.*)\\]$"), lambda m: "giá trị '%s' không thuộc danh sách cho phép: %s" % (m.group("v"), m.group("opts"))),
	(re.compile(r"^(?P<v>.+) is not of type '(?P<t>.+)'$"), lambda m: "giá trị %s không đúng kiểu (cần: %s)" % (m.group("v"), m.group("t"))),
	(re.compile(r"^(?P<v>.+) is less than the minimum of (?P<mn>.+)$"), lambda m: "giá trị %s nhỏ hơn mức tối thiểu %s" % (m.group("v"), m.group("mn"))),
	(re.compile(r"^(?P<v>.+) is greater than the maximum of (?P<mx>.+)$"), lambda m: "giá trị %s lớn hơn mức tối đa %s" % (m.group("v"), m.group("mx"))),
	(re.compile(r"^(?P<v>.+) is too short$"), lambda m: "giá trị %s quá ngắn" % m.group("v")),
	(re.compile(r"^(?P<v>.+) is too long$"), lambda m: "giá trị %s quá dài" % m.group("v")),
	(re.compile(r"^Additional properties are not allowed \\((?P<ex>.*) was unexpected\\)$"), lambda m: "không cho phép tham số %s" % m.group("ex")),
)
def _translate_message(message: str) -> str:
	"""Dich message cua jsonschema sang tieng Viet (fallback: tra nguyen ban)."""
	text = str(message or "").strip()
	for pattern, replacer in _MSG_RULES:
		match = pattern.match(text)
		if match:
			return replacer(match)
	return text

class ToolSpec:
    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Handler,
        required_powers: Optional[List[str]] = None,
        required_headers: Optional[List[int]] = None,
    ):
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler
        # list định danh power cần thiết — int/chuỗi số = SystemPower.id,
        # chuỗi khác = SystemPower.power_en (exact) — theo _0039/_0040.
        self.required_powers = required_powers or []
        # list SystemHeader.id mà user bắt buộc có quyền mới được gọi tool.
        # Rỗng = tool không gắn với dữ liệu header nào.
        self.required_headers = required_headers or []

    # ------------------------------------------------------------------
    # Kiểm soát truy cập
    # ------------------------------------------------------------------
    def is_available_to(self, user) -> bool:
        """User có đủ quyền power VÀ header không?

        Rỗng điều kiện → True (tool không yêu cầu quyền gì).

        KHÔNG nuốt exception ở đây: nếu DB lỗi mà trả `False` thì lỗi hệ
        thống bị báo thành "bạn không có quyền" — sai sự thật và rất khó truy lỗi.
        Cứ để exception nổi lên:
          - `call()` bọc lại và trả về nội dung lỗi thật (vẫn fail-closed, không
            chạy handler);
          - `AIMCPService.list_tools` / `get_tool` đã tự try/except theo từng tool nên tool
            lỗi quyền chỉ bị ẨN khỏi danh sách, không làm sụp cả danh sách.
        """
        if self.required_powers and not has_power(user, self.required_powers):
            return False
        for header_id in self.required_headers:
            # import trong hàm: apps.info.permissions kẹ vòng import với apps.ai.
            from apps.info.permissions import user_has_header_permission

            if not user_has_header_permission(user, header_id):
                return False
        return True

    def validate_args(self, args: Optional[Dict[str, Any]]) -> Optional[str]:
        """Validate args theo JSON Schema.

        Trả ``None`` = hợp lệ; trả chuỗi = thông báo lỗi cho model/UI.

        Cần vì args do AI (không phải người viết ra) — LLM hay tự
        đảo ngược id, số thành string, bỏ qua field required...
        Không validate thì tool dễ crash, hoặc đọc nhầng giá không
        nằm trong phạm vi quyền của user.
        """
        schema = self.input_schema or {}
        if not isinstance(schema, dict) or not schema:
            return None
        try:
            from jsonschema import Draft7Validator
        except ImportError:
            # Thiếu jsonschema: KHÔNG chặn cách (fail-open) để tool vẫn chạy,
            # nhưng phải rõ ràng trong log để không im lặng bỏ qua validation.
            logger.warning("Thiếu jsonschema — BỎ QUA validation cho tool %s", self.name)
            return None

        try:
            errors = sorted(Draft7Validator(schema).iter_errors(args or {}), key=lambda e: list(e.path))
        except Exception:  # noqa: BLE001 — schema hỏng dẽ đươc ghi sai
            logger.exception("Tool %s: input_schema không hợp lệ", self.name)
            return None
        if not errors:
            return None

        first = errors[0]
        path = "/".join(str(part) for part in first.path) or "(root)"
        # Ghi thêm số lỗi để AI biết lại và sửa tham số (thường model sửa được ngay).
        extra = f" (còn {len(errors)} lỗi khác)" if len(errors) > 1 else ""
        return f"Tham số '{path}' không hợp lệ: {_translate_message(first.message)}{extra}"

    def call(self, user, args: Optional[Dict[str, Any]]):
        """Chạy tool: quyền → validate schema → handler.

        Mọi exception (kể cả lỗi kiểm tra quyền) đều được bọc lại
        → trả error content thay vì để lộ 500 / stacktrace (S3).
        """
        try:
            if not self.is_available_to(user):
                return _error_result(DENIED_TEXT)

            args = args or {}
            invalid = self.validate_args(args)
            if invalid:
                return _error_result(invalid)

            return self.handler(user, args)
        except Exception as exc:  # noqa: BLE001 - chặn mọi lỗi tool
            logger.exception("Tool %s failed", self.name)
            return _error_result(f"Tool '{self.name}' gặp lỗi: {exc}")

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

    # ---- schema dùng cho MCP tab / Form tab (FE render form từ schema) ----
    def to_mcp_tool(self) -> Dict[str, Any]:
        """Tool definition chuẩn MCP: name/description/inputSchema.

        FE dùng `inputSchema` để sinh form động (tab Form) và hiển thị card
        tool (tab MCP) — cùng một nguồn schema, không phải khai hai lần.
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "required_powers": list(self.required_powers),
            "required_headers": list(self.required_headers),
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