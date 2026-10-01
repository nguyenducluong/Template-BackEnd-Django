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

from .tools.registry import execute_tool

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

        # Lọc tool theo QUYỀN của user TRƯỚC khi đưa cho model. Nếu không lọc:
        # model vẫn thấy tên + sơ đồ của mọi tool → lộ tool ngoài phạm vi và tốn
        # lượt gọi cho các tool chắc chắn trả "không có quyền".
        # `execute_tool` vẫn kiểm tra quyền lần nữa khi thực thi → fail-closed.
        allowed = self._allowed_specs(user)
        allowed_names = {spec.name for spec in allowed}

        tool_prompt = NATIVE_TOOL_PROMPT if self.use_native_tools else self._json_prompt(allowed)

        has_sys = any(m.get("role") == "system" for m in messages)
        if not has_sys:
            messages = [{"role": "system", "content": tool_prompt}] + messages
        else:
            for m in messages:
                if m.get("role") == "system":
                    m["content"] = (m.get("content", "") + "\n\n" + tool_prompt)
                    break

        for _ in range(self.max_turns):
            tools = [spec.to_ollama_tool() for spec in allowed] if self.use_native_tools else None
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
                call = self._parse_json_call(content, allowed_names)
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
    @staticmethod
    def _allowed_specs(user) -> list:
        """Tool mà user ĐƯỢC gọi — lọc qua AIMCPService (nguồn duy nhất về quyền)."""
        from .services import get_ai_mcp_service

        return get_ai_mcp_service().list_tools(user)

    @staticmethod
    def _json_prompt(allowed: list) -> str:
        lines = []
        for spec in sorted(allowed, key=lambda s: s.name):
            params = json.dumps(spec.input_schema, ensure_ascii=False)
            lines.append(f"- {spec.name}: {spec.description} | args_schema={params}")
        # Không có tool nào được quyền → nói rõ để model trả lời tự nhiên thay vì
        # bịa tên tool.
        if not lines:
            return JSON_TOOL_PROMPT.format(tools="- (không có công cụ nào khả dụng)")
        return JSON_TOOL_PROMPT.format(tools="\n".join(lines))

    @staticmethod
    def _parse_json_call(content: str, allowed_names: set) -> Optional[Dict[str, Any]]:
        """Trích JSON {"tool":..., "args":...} từ text của model.

        Model hay trả lẫn JSON với văn xuôi ("Here's the request: ```json {...}```"),
        thậm chí có nhiều khối JSON trong một câu. Cách cũ cắt từ `{` ĐẦU TIÊN tới
        `}` CUỐI CÙNG nên gộp cả các khối lại thành chuỗi hỏng -> luôn None ->
        agent trả nguyên văn bản thô cho người dùng thay vì gọi tool.

        Nay dùng `raw_decode` thử lần lượt TỪNG vị trí `{`: khối JSON hợp lệ đầu
        tiên sẽ được lấy đúng, kể cả khi có khối khác nằm trước/sau.
        """
        text = (content or "").strip()

        data = None
        decoder = json.JSONDecoder()
        index = text.find("{")
        while index != -1:
            try:
                candidate, _ = decoder.raw_decode(text, index)
            except ValueError:
                candidate = None
            if isinstance(candidate, dict) and "tool" in candidate:
                data = candidate
                break
            index = text.find("{", index + 1)

        if data is None:
            return None
        if not isinstance(data, dict) or "tool" not in data:
            return None
        # Chỉ chấp nhận tool user được phép (chặn model bịa / gọi tool ngoài quyền)
        if data["tool"] not in allowed_names:
            return None
        return {"tool": data["tool"], "args": data.get("args", {})}