"""
ToolAgent — vòng lặp cho phép AI trong Django gọi tool để đọc/phân tích dữ liệu.

Cơ chế:
  1. Gửi messages (+ danh sách tool) tới Ollama.
  2. Native `message.tool_calls` -> execute -> append kết quả -> lặp.
  3. JSON fallback: model trả `{"tool", "args"}` -> execute -> lặp.
  4. Hết vòng (max_turns) hoặc không còn tool_call -> trả text cuối.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from libs.ai.ollama_client import OllamaClient

from .tools.registry import ALLOWED_TOOL_NAMES, execute_tool, list_tools_schemas

logger = logging.getLogger("apps")

JSON_TOOL_PROMPT = (
    "Bạn được phép gọi các \"tool\" để đọc dữ liệu hệ thống.\n"
    "Danh sách tool (name + input args):\n"
    "{tools}\n\n"
    "QUY TẮC GỌI TOOL:\n"
    "- Khi cần dữ liệu từ tool, hãy trả về DUY NHẤT một JSON hợp lệ dạng:\n"
    "  {{\"tool\": \"<tool_name>\", \"args\": {{...các tham số...}}}}\n"
    "- KHÔNG ghi thêm chữ/comment nào ngoài JSON đó.\n"
    "- Nếu đã có kết quả tool (tin nhắn role 'tool'), hãy tổng hợp và trả lời "
    "bằng văn bản bình thường cho người dùng.\n"
    "- Không bịa dữ liệu; nếu tool không cho kết quả, nói rõ là không có."
)

NATIVE_TOOL_PROMPT = (
    "Bạn được phép gọi tool để đọc dữ liệu hệ thống. "
    "Chỉ gọi tool khi thật sự cần dữ liệu; ngược lại trả lời bình thường."
)


def _normalize_result(result, name: str) -> Dict[str, Any]:
    """Chuẩn hóa kết quả tool về dạng MCP content text."""
    if isinstance(result, dict) and "content" in result and isinstance(result.get("content"), list):
        return result
    if isinstance(result, (dict, list)):
        try:
            text = json.dumps(result, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            text = str(result)
    else:
        text = str(result)
    return {"content": [{"type": "text", "text": text}]}


class ToolAgent:
    def __init__(self, client: Optional[OllamaClient] = None, max_turns: int = 3,
                 use_native_tools: bool = False):
        self.client = client or OllamaClient()
        self.max_turns = max_turns or 1
        self.use_native_tools = use_native_tools

    # ------------------------------------------------------------------
    def run(self, messages: List[Dict[str, str]], user=None) -> str:
        """Chạy vòng lặp tool. Trả về text phản hồi cuối cùng."""
        messages = [dict(m) for m in messages]
        tool_prompt = NATIVE_TOOL_PROMPT if self.use_native_tools else self._json_prompt()

        has_sys = any(m.get("role") == "system" for m in messages)
        if not has_sys:
            messages = [{"role": "system", "content": tool_prompt}] + messages
        else:
            for m in messages:
                if m.get("role") == "system":
                    m["content"] = (m.get("content", "") + "\n\n" + tool_prompt)
                    break

        for _ in range(self.max_turns):
            tools = list_tools_schemas() if self.use_native_tools else None
            response = self.client.chat(messages, tools=tools)
            reply = response.get("message", {})
            content = reply.get("content", "") or ""

            # 1) Native tool_calls
            tool_calls = reply.get("tool_calls") or []
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    name = fn.get("name", "")
                    args = fn.get("arguments", {}) or {}
                    self._execute_and_collect(messages, user, name, args)
                continue  # tổng hợp ở lượt sau

            # 2) JSON fallback
            if not self.use_native_tools:
                call = self._parse_json_call(content)
                if call is not None:
                    self._execute_and_collect(messages, user, call["tool"], call["args"])
                    continue

            return content

        return "Tôi đã đạt giới hạn vòng lặp tool. Vui lòng thử lại với câu hỏi cụ thể hơn."

    # ------------------------------------------------------------------
    def _execute_and_collect(self, messages, user, name: str, args: Dict) -> None:
        result = execute_tool(name, user, args or {})
        normalized = _normalize_result(result, name)
        messages.append({"role": "assistant", "content": f"Gọi tool: {name}"})
        messages.append({
            "role": "tool",
            "content": json.dumps(normalized.get("content", []), ensure_ascii=False),
        })
        logger.info("Agent tool called: %s by user=%s", name, getattr(user, "id", None))

    # ------------------------------------------------------------------
    def _json_prompt(self) -> str:
        from .tools.registry import TOOLS

        lines = []
        for name in sorted(ALLOWED_TOOL_NAMES):
            spec = TOOLS[name]
            params = json.dumps(spec.input_schema, ensure_ascii=False)
            lines.append(f"- {name}: {spec.description} | args_schema={params}")
        return JSON_TOOL_PROMPT.format(tools="\n".join(lines))

    @staticmethod
    def _parse_json_call(content: str) -> Optional[Dict[str, Any]]:
        """Trích JSON {"tool":..., "args":...} từ text model (bỏ wrapper ```json)."""
        text = content.strip()
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                data = json.loads(content[start:end + 1])
            except (ValueError, TypeError):
                return None
        if not isinstance(data, dict) or "tool" not in data:
            return None
        if data["tool"] not in ALLOWED_TOOL_NAMES:
            return None
        return {"tool": data["tool"], "args": data.get("args", {})}