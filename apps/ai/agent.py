"""
ToolAgent — vòng lặp cho phép AI trong Django gọi tool để đọc/phân tích dữ liệu.

Cơ chế (theo thứ tự ưu tiên):
  1. NATIVE tool-calling (`message.tool_calls`) — đường CHÍNH, model tự sinh
     lệnh gọi đúng chuẩn Ollama/OpenAI, không phải dạy model viết JSON tay.
  2. JSON fallback (`{"tool", "args"}`) — chỉ khi `use_native_tools=False`.
  3. Hết vòng (`max_turns`) hoặc không còn tool_call -> trả text cuối.

HAI LỐI CHẠY:
  - `run()`        : blocking, trả chuỗi (test / gọi nội bộ).
  - `run_stream()` : generator phát SỰ KIỆN từng bước. Đây là đường dùng cho
    HTTP: nhờ vậy user thấy chữ NGAY (không phải chờ agent chạy xong rồi mới
    cắt 24 ký tự), và thấy được tool nào đang được gọi.

Sự kiện `run_stream()` phát ra (dict):
  {"type": "status",    "text": "...", "turn": int}
  {"type": "tool_call", "name": "...", "arguments": {...}, "is_error": bool}
  {"type": "content",   "text": "..."}
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Generator, List, Optional

from django.conf import settings

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
    "Bạn là trợ lý AI của hệ thống nội bộ.\n"
    "- Cần dữ liệu nào không có trong câu hỏi thì gọi tool tương ứng "
    "(mỗi lần chỉ 1 tool, đợi kết quả rồi mới quyết định bước sau).\n"
    "- Sau khi đã có kết quả tool, PHẢI tổng hợp thành câu trả lời tiếng Việt "
    "cho người dùng. Tuyệt đối không in tên tool, không in cú pháp JSON, "
    "không viết kiểu 'Gọi tool: ...'.\n"
    "- Không bịa số liệu. Tool không có kết quả thì nói rõ là không có."
)

# Số ký tự tool-result tối đa đưa vào lượt sau — chặn context nổ khi tool trả
# danh sách dài (org_tree, header_structure...).
MAX_TOOL_RESULT_CHARS = 4000


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


def _result_to_text(result, name: str) -> str:
    """Kết quả tool (đã normalize) -> chuỗi đưa vào messages, có cắt bớt."""
    normalized = _normalize_result(result, name)
    parts = [item["text"] for item in (normalized.get("content") or [])
             if isinstance(item, dict) and isinstance(item.get("text"), str)]
    text = "\n".join(parts) or json.dumps(normalized, ensure_ascii=False, default=str)
    if len(text) > MAX_TOOL_RESULT_CHARS:
        text = text[:MAX_TOOL_RESULT_CHARS] + "\n...(còn nữa, đã cắt bớt)"
    return text


class ToolAgent:
    def __init__(self, client: Optional[OllamaClient] = None, max_turns: int = 3,
                 use_native_tools: bool = True):
        self.client = client or OllamaClient()
        self.max_turns = max_turns or 1
        # Native tool-calling mặc định BẬT (xem `run_stream`).
        self.use_native_tools = use_native_tools
        self.options = self._build_options()

    @staticmethod
    def _build_options() -> Dict[str, Any]:
        """Tham số sinh: temperature thấp + giới hạn độ dài.

        - `temperature` mặc định 0.2: tool-calling cần tính xác định, không bịa.
        - `num_predict`: chặn model trả quá dài, bảo vệ timeout gunicorn.
        """
        options: Dict[str, Any] = {"temperature": float(getattr(settings, "AI_TEMPERATURE", 0.2))}
        num_predict = getattr(settings, "AI_NUM_PREDICT", None)
        if num_predict:
            options["num_predict"] = int(num_predict)
        return options

    # ------------------------------------------------------------------
    def run(self, messages: List[Dict[str, str]], user=None) -> str:
        """Chạy vòng lặp tool, trả về TEXT ĐẦY ĐỦ của lượt trả lời cuối.

        Phải NỐI tất cả chunk `content` lại: `run_stream` cắt text thành nhiều
        đoạn 24 ký tự để client nhận dần. Nếu chỉ giữ đoạn cuối thì kết quả
        chỉ còn vài ký tự cuối.
        """
        parts: List[str] = []
        for event in self.run_stream(messages, user):
            if event.get("type") == "content":
                parts.append(event.get("text", ""))
        return "".join(parts)

    # ------------------------------------------------------------------
    def _stream_turn(self, messages, tools):
        """Lấy nội dung của MỘT lượt từ client, dạng sự kiện.

        Ưu tiên `chat_stream_events` (có `tool_calls`). Nhưng client có thể chỉ
        cài `chat` kiểu blocking — ví dụ test cũ, hoặc backend AI khác — nên khi
        lượt đó KHÔNG sinh event nào thì gọi `chat` và bọc kết quả về cùng định
        dạng. Nhờ vậy agent chạy được với CẢ hai kiểu client.

        LƯU Ý: phải kiểm tra theo "có event hay không" chứ không dựa vào
        exception — `unittest.mock.MagicMock` iterable nên lặp ra 0 phần tử mà
        không ném lỗi, khiến fallback theo `except` không bao giờ chạy.
        """
        try:
            events = list(self.client.chat_stream_events(messages, options=self.options, tools=tools))
        except TypeError:
            events = None  # client không hỗ trợ streaming

        if events:
            yield from events
            return

        reply = self.client.chat(messages, tools=tools) or {}
        message = reply.get("message") or {}
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or []
        if content or tool_calls:
            yield {"content": content, "tool_calls": tool_calls}

    def run_stream(self, messages: List[Dict[str, str]], user=None) -> Generator[Dict[str, Any], None, None]:
        """Chạy agent và phát sự kiện từng bước (status / tool_call / content)."""
        messages = [dict(m) for m in messages]

        # Lọc tool theo QUYỀN của user TRƯỚC khi đưa cho model. Nếu không lọc:
        # model vẫn thấy tên + sơ đồ của mọi tool → lộ tool ngoài phạm vi và tốn
        # lượt gọi cho các tool chắc chắn trả "không có quyền".
        # `execute_tool` kiểm tra quyền lần nữa khi thực thi → fail-closed.
        allowed = self._allowed_specs(user)
        allowed_names = {spec.name for spec in allowed}

        # Không có tool nào được phép → tắt tool hoàn toàn: tránh tốn context và
        # tránh model "bịa" tên tool không có thật.
        if not allowed:
            self.use_native_tools = False

        tool_prompt = NATIVE_TOOL_PROMPT if self.use_native_tools else self._json_prompt(allowed)
        messages = self._inject_system_prompt(messages, tool_prompt)

        yield {"type": "status", "text": "Đang phân tích câu hỏi...", "turn": 0}

        last_text = ""
        for turn in range(self.max_turns):
            turn_tools = [spec.to_ollama_tool() for spec in allowed] if self.use_native_tools else None
            buffered: List[str] = []
            tool_calls: List[Dict[str, Any]] = []

            for event in self._stream_turn(messages, turn_tools):
                if event.get("tool_calls"):
                    tool_calls.extend(event["tool_calls"])
                content = event.get("content") or ""
                if content:
                    # CHỈ BỘ ĐỆM chứ chưa phát: native tool-calling đẩy
                    # tool_calls ở frame `done` cuối, tức lúc này chưa biết
                    # model có gọi tool không. Phát sớm sẽ bị trùng ("Gọi tool:
                    # x") — đúng lỗi model nhỏ hay mắc.
                    buffered.append(content)

            if tool_calls:
                for call in self._normalize_tool_calls(tool_calls):
                    name = call.get("name") or ""
                    if name not in allowed_names:
                        logger.warning("Agent từ chối tool ngoài phạm vi: %s", name)
                        continue
                    result = execute_tool(name, user, call.get("arguments") or {})
                    messages.append({"role": "tool", "content": _result_to_text(result, name)})
                    yield {
                        "type": "tool_call",
                        "name": name,
                        "arguments": call.get("arguments") or {},
                        "is_error": bool(isinstance(result, dict) and result.get("isError")),
                    }
                    logger.info("Agent tool called: %s by user=%s", name, getattr(user, "id", None))
                continue  # tổng hợp ở lượt sau

            text = "".join(buffered)

            # JSON fallback: model tự viết {"tool": ..., "args": ...} trong text.
            if not tool_calls:
                call = self._parse_json_call(text, allowed_names)
                if call is not None:
                    result = execute_tool(call["tool"], user, call["args"])
                    messages.append({"role": "tool", "content": _result_to_text(result, call["tool"])})
                    yield {
                        "type": "tool_call",
                        "name": call["tool"],
                        "arguments": call["args"],
                        "is_error": bool(isinstance(result, dict) and result.get("isError")),
                    }
                    continue

            last_text = text
            if text:
                # Lượt này có text mà không có tool_call ⇒ đây là lượt trả lời
                # cuối. Cắt nhỏ để FE nhận dần (chữ chạy thật, không nhảy cụt).
                for i in range(0, len(text), 24):
                    yield {"type": "content", "text": text[i:i + 24]}
                return

        if not last_text:
            yield {
                "type": "content",
                "text": "Tôi đã đạt giới hạn vòng lặp tool. Vui lòng thử lại với câu hỏi cụ thể hơn.",
            }

    # ------------------------------------------------------------------
    @staticmethod
    def _inject_system_prompt(messages: List[Dict[str, str]], tool_prompt: str) -> List[Dict[str, str]]:
        """Gắn prompt hệ thống, hoặc nối vào system sẵn có."""
        for m in messages:
            if m.get("role") == "system":
                m["content"] = (m.get("content", "") + "\n\n" + tool_prompt)
                return messages
        return [{"role": "system", "content": tool_prompt}, *messages]

    @staticmethod
    def _normalize_tool_calls(tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Chuẩn hóa tool_call Ollama/OpenAI về {name, arguments} dict.

        `arguments` có thể là dict (đa số server) hoặc chuỗi JSON (model nhỏ hay
        trả kiểu này) -> parse lại; hỏng thì `{}` để validate_args bắt lỗi.
        """
        normalized = []
        for call in tool_calls or []:
            if not isinstance(call, dict):
                continue
            fn = call.get("function") or {}
            name = (fn.get("name") or "").strip()
            if not name:
                continue
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args.strip() else {}
                except ValueError:
                    args = {}
            if not isinstance(args, dict):
                args = {}
            normalized.append({"name": name, "arguments": args})
        return normalized

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