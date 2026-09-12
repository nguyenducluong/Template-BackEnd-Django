# MCP server — bridges Django AI tool registry (apps.ai.tools) into a real MCP server.

"""
# MCTS / Plan backward
## Why: Các agent LLMs bên ngoài (Claude Desktop, Continue, Windsurf…) chỉ
## đọc được 1 chuẩn duy nhất: MCP protocol (JSON-RPC tool/list, tool/call…).
## Code hiện tại ở `apps/ai` đã sẵn sàng: có ToolSpec/prompt/Serialize/powers bằng JWT.
## Cần một MCP Server verdad để client ngoài kết nối được, bonus:
##  - MCP SSE = StreamingHttpResponse giàu hơn context, trọng dụng thread.
##  - Giúp user “ai terlalu” tương tác: call tool via `/api/v1/ai/mcp/`.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from django.http import HttpRequest, HttpResponse

from .tools.registry import TOOLS

logger = logging.getLogger("apps")

MESSAGE_TOOLS_LIST = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "result": {"tools": []},
}

MESSAGE_TOOL_CALL = {
    "jsonrpc": "2.0",
    "id": None,
    "method": None,
    "params": {},
    "result": None,
}


def _build_mcp_tools_list() -> list:
    """Return MCP-format tool definitions for all registered tools."""
    out: list = []
    for spec in TOOLS.values():
        tool = {
            "name": spec.name,
            "description": spec.description,
            "inputSchema": spec.input_schema,
        }
        out.append(tool)
    return out


def _mcp_envelope(text_body: str) -> str:
    """Wrap a JSON-RPC response in SSE-style framing for MCP client."""
    return f"data: {text_body}\n\n"


def mcp_tools_list(user: Any) -> str:
    """tools/list: trả danh sách tool schema (dùng cho client bóc tách)."""
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list",
            "result": {"tools": _build_mcp_tools_list()}}
    return _mcp_envelope(json.dumps(body, ensure_ascii=False, default=str))


def mcp_tools_call(user: Any, payload: Dict[str, Any]) -> str:
    """tools/call: dispatch tới ToolSpec.execute, trả MCP result/jsonrpc message."""
    method: Optional[str] = payload.get("method")
    params: Dict[str, Any] = payload.get("params", {}) or {}
    req_id: Any = payload.get("id", 1)

    if not method:
        err = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32600,
                   "message": "Missing method", "data": "method yêu cầu"}}
        return _mcp_envelope(json.dumps(err, ensure_ascii=False, default=str))

    if method not in ("tools/call", "tools/list"):
        err = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601,
                   "message": "Method not found", "data": method}}
        return _mcp_envelope(json.dumps(err, ensure_ascii=False, default=str))

    if method == "tools/list":
        return mcp_tools_list(user)

    # ---- tools/call --------------------------------------------------------
    name: Optional[str] = str(params.get("name", "")).strip()
    arguments: Dict[str, Any] = params.get("arguments", {}) or {}

    if not name:
        err = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602,
                   "message": "Missing tool name", "data": ""}}
        return _mcp_envelope(json.dumps(err, ensure_ascii=False, default=str))

    from ..tools.base import ToolSpec

    spec = TOOLS.get(name)
    if spec is None:
        err = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601,
                   "message": f"Tool '{name}' không tồn tại", "data": name}}
        return _mcp_envelope(json.dumps(err, ensure_ascii=False, default=str))

    # tool.call trả MCP content `content` — chuẩn hóa về jsonrpc result.
    result = spec.call(user, arguments)

    # Nếu error nội tại (ToolSpec đã bọc), nhưng vẫn trả JSON-RPC thành công
    # với error content trong result — MCP client đọc được.
    body = {"jsonrpc": "2.0", "id": req_id, "result": result}
    return _mcp_envelope(json.dumps(body, ensure_ascii=False, default=str))