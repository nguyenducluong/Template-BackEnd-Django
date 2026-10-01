"""
AIMCPService — lớp dịch vụ DUY NHẤT cho mọi nơi gọi tool AI.

Vì sao cần lớp này (thay vì gọi thẳng registry ở mỗi view):
  - Agent chat, tab MCP, tab Form và client MCP bên ngoài đều phải thấy
    CÙNG một danh sách tool và CÙNG một logic quyền. Nếu mỗi chỗ tự
    lọc, sẽ xảy ra "chat thấy tool mà tab MCP không thấy" → FE và BE lệch.
  - Chỗ duy nhất ánh xạ JSON Schema → form động (Form tab), để không
    phải viết lại logic đọc schema ở FE lẫn BE.
  - Chỗ duy nhất gắn nhãn đa ngôn ngữ cho form.

Nguyên tắc: mọi lọc quyền đều thực hiện ở đây và ở ToolSpec.call —
UI chỉ hiển thị, không bao giờ là hàng rào bảo mật.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .tools.base import ToolSpec
from .tools.registry import TOOLS

logger = logging.getLogger("apps")

# Ngôn ngữ app hỗ trợ — thứ tự ưu tiên khi suy ra nhãn.
LOCALES = ("vi", "en", "kr")

# Kiểu JSON Schema -> kiểu input phía FE (MUI).
_SCHEMA_TYPE_TO_UI = {
    "string": "text",
    "number": "number",
    "integer": "number",
    "boolean": "switch",
    "array": "text",
    "object": "text",
}


class AIMCPService:
    """Dịch vụ MCP dùng chung — thread-safe, không giữ state theo user."""

    # ------------------------------------------------------------------
    # Cổng bật/tắt
    # ------------------------------------------------------------------
    @staticmethod
    def is_enabled() -> bool:
        """Chatbot có được bật không (settings.AI_CHAT_ENABLED).

        Đọc mỗi lần gọi (không cache ở module) để đổi flag trong .env
        rồi restart được, không phải sửa code.
        """
        from django.conf import settings

        return bool(getattr(settings, "AI_CHAT_ENABLED", False))

    # ------------------------------------------------------------------
    # Truy vấn tool
    # ------------------------------------------------------------------
    def list_tools(self, user) -> List[ToolSpec]:
        """Tool mà *user* ĐƯỢC gọi (đã lọc theo power + header).

        Lọc ở đây để tab MCP/Form không hiện tool user không gọi được;
        nhưng vẫn phải kiểm tra lần nữa trong ToolSpec.call khi thực thi.
        """
        # Cờ tắt => không lộ bất kỳ tool nào, kể cả schema cho model/client ngoài.
        if not self.is_enabled():
            return []
        allowed = []
        for spec in TOOLS.values():
            try:
                if spec.is_available_to(user):
                    allowed.append(spec)
            except Exception:  # noqa: BLE001 — lỗi quyền thì ẩn tool, không làm sập list
                logger.exception("Lỗi kiểm tra quyền tool %s", spec.name)
        return allowed

    def list_tools_schemas(self, user) -> List[Dict[str, Any]]:
        """Danh sách tool dạng MCP (name/description/inputSchema) cho user."""
        return [spec.to_mcp_tool() for spec in self.list_tools(user)]

    def list_tools_schemas_ollama(self, user) -> List[Dict[str, Any]]:
        """Danh sách tool dạng native tool-calling (Ollama/OpenAI format).

        Chỉ trả tool user gọi được — đừng "hy vọng model tự không gọi",
        vẫn có ToolSpec.call chặn nhưng đừng lãng phí context của model.
        """
        return [spec.to_ollama_tool() for spec in self.list_tools(user)]

    def get_tool(self, name: str, user) -> Optional[ToolSpec]:
        """Tool theo tên, hoặc None nếu không tồn tại / user không có quyền."""
        spec = TOOLS.get(name)
        if spec is None:
            return None
        try:
            return spec if spec.is_available_to(user) else None
        except Exception:  # noqa: BLE001
            logger.exception("Lỗi kiểm tra quyền tool %s", name)
            return None

    # ------------------------------------------------------------------
    # Thực thi
    # ------------------------------------------------------------------
    def execute(self, name: str, user, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Gọi tool theo tên. Luôn trả MCP-style dict, không bao giờ ném lỗi ra ngoài."""
        if not self.is_enabled():
            return self._error("Tính năng AI hiện đang tắt (AI_CHAT_ENABLED).")
        spec = TOOLS.get(name)
        if spec is None:
            return self._error(f"Tool '{name}' không tồn tại.")
        # ToolSpec.call tự kiểm tra quyền + validate schema + bọc exception.
        return spec.call(user, args or {})

    @staticmethod
    def _error(message: str) -> Dict[str, Any]:
        return {"isError": True, "content": [{"type": "text", "text": message}]}

    # ------------------------------------------------------------------
    # JSON-RPC (MCP protocol) — cho client ngoài và tab MCP
    # ------------------------------------------------------------------
    def mcp_tools_list(self, user, request_id: Any = 1) -> Dict[str, Any]:
        """method=tools/list — MCP chuẩn, trả về dict JSON-RPC (chưa stringify)."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/list",
            "result": {"tools": self.list_tools_schemas(user)},
        }

    def mcp_tools_call(self, user, payload: Dict[str, Any]) -> Dict[str, Any]:
        """method=tools/call — MCP chuẩn."""
        payload = payload or {}
        params = payload.get("params") or {}
        name = params.get("name") or ""
        args = params.get("arguments") or {}
        if not name:
            return self._mcp_error(payload.get("id", 1), -32602, "Missing tool name", "")
        return {
            "jsonrpc": "2.0",
            "id": payload.get("id", 1),
            "method": payload.get("method", "tools/call"),
            "result": self.execute(name, user, args),
        }

    @staticmethod
    def _mcp_error(request_id, code: int, message: str, data=None) -> Dict[str, Any]:
        """Gói lỗi JSON-RPC 2.0 (chưa stringify)."""
        error: Dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return {"jsonrpc": "2.0", "id": request_id, "error": error}

    def mcp_dispatch(self, user, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatcher JSON-RPC cho tab MCP / client ngoài.

        Đây là chỗ DUY NHẤT cài giao thức MCP. Trước đây còn có `mcp_server.py`
        với logic tương tự nhưng không nơi nào import → đã gộp về đây.
        """
        payload = payload or {}
        request_id = payload.get("id", 1)
        method = str(payload.get("method") or "").strip()
        if not method:
            return self._mcp_error(request_id, -32600, "Missing method", "method là bắt buộc")
        if method not in ("tools/list", "tools/call"):
            return self._mcp_error(request_id, -32601, "Method not found", method)
        if method == "tools/list":
            return self.mcp_tools_list(user, request_id)
        return self.mcp_tools_call(user, payload)

    # ------------------------------------------------------------------
    # Form động (tab Form) — server-driven, không hardcode ở FE
    # ------------------------------------------------------------------
    def build_form(self, name: str, user) -> Optional[Dict[str, Any]]:
        """Dựng form cho 1 tool từ JSON Schema. None nếu tool không truy cập được.

        Output là mảng field đã chuẩn hoá — FE chỉ cần map sang MUI, không
        phải hiểu JSON Schema.

        Mở rộng `ui` (tuỳ chọn, KHÔNG phá MCP): mỗi property có thể khai
            "ui": {"widget": "select", "rows": 4, "placeholder": "..."}
        Field nào không khai thì suy ra từ type/enum/min-max.
        """
        if not self.is_enabled():
            return None
        spec = self.get_tool(name, user)
        if spec is None:
            return None

        schema = spec.input_schema or {}
        properties: Dict[str, Any] = schema.get("properties") or {}
        required = set(schema.get("required") or [])

        fields = [self._build_field(key, prop or {}, key in required) for key, prop in properties.items()]

        # required_list theo thứ tự khai báo (ổn định cho test + UI).
        required_list = [key for key in properties if key in required]

        return {
            "name": spec.name,
            "description": spec.description,
            "fields": fields,
            "required": required_list,
            "submit_label": "Chạy " + spec.name,
        }

    def _build_field(self, key: str, prop: Dict[str, Any], is_required: bool) -> Dict[str, Any]:
        """JSON Schema property -> field descriptor cho FE."""
        json_type = prop.get("type", "string")
        ui_ext: Dict[str, Any] = prop.get("ui") or {}

        # Ưu tiên enum -> select, trừ khi `ui` ép widget khác.
        if prop.get("enum") and not ui_ext.get("widget"):
            widget = "select"
        else:
            widget = ui_ext.get("widget") or _SCHEMA_TYPE_TO_UI.get(json_type, "text")

        field: Dict[str, Any] = {
            "key": key,
            "label": self._label(prop, key),
            "widget": widget,
            "type": json_type,
            "required": is_required,
        }

        # default phải copy (không trỏ vào dict schema gốc) để FE sửa không
        # làm bẩn ToolSpec dùng chung cho mọi request.
        if "default" in prop:
            field["default"] = prop["default"]
        if prop.get("enum"):
            field["options"] = self._options(prop["enum"])
        if prop.get("description"):
            field["help"] = prop["description"]
        if ui_ext.get("placeholder"):
            field["placeholder"] = ui_ext["placeholder"]
        if ui_ext.get("rows"):
            field["rows"] = ui_ext["rows"]

        # Ràng buộc số — FE dùng để set min/max.
        if json_type in ("number", "integer"):
            if "minimum" in prop:
                field["min"] = prop["minimum"]
            if "maximum" in prop:
                field["max"] = prop["maximum"]
            field["step"] = 1 if json_type == "integer" else "any"

        return field

    @staticmethod
    def _label(prop: Dict[str, Any], fallback: str) -> Any:
        """Nhãn đa ngôn ngữ.

        `title` có thể là chuỗi (đơn ngữ) hoặc object {vi,en,kr} (đa ngữ).
        Trả về đúng kiểu đầu vào để FE tự chọn theo locale hiện tại.
        """
        title = prop.get("title")
        if isinstance(title, dict):
            return {loc: title.get(loc) or title.get("en") or fallback for loc in LOCALES}
        return title or fallback

    @staticmethod
    def _options(enum: List[Any]) -> List[Dict[str, Any]]:
        """Enum -> [{value, label}] cho Select của MUI."""
        return [{"value": item, "label": str(item)} for item in enum]

    # ------------------------------------------------------------------
    # Meta cho FE
    # ------------------------------------------------------------------
    def meta(self, user) -> Dict[str, Any]:
        """Thông tin FE cần để dựng khung chatbot (nhãn đa ngôn ngữ, cờ bật)."""
        from django.conf import settings

        tools = self.list_tools(user)
        return {
            "locales": list(LOCALES),
            "tools": [{"name": s.name, "description": s.description} for s in tools],
            "model": getattr(settings, "OLLAMA_MODEL", ""),
            "embedding_model": getattr(settings, "AI_EMBEDDING_MODEL", ""),
            "chat_enabled": bool(getattr(settings, "AI_CHAT_ENABLED", False)),
        }


# Singleton — service stateless nên 1 instance cho cả process là đủ.
_service = AIMCPService()


def get_ai_mcp_service() -> AIMCPService:
    """Lấy instance dùng chung. Import trong hàm để tránh vòng import."""
    return _service