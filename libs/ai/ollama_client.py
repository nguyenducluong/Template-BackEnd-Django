"""
Ollama HTTP client (reusable, framework-agnostic).

Talks to a local/remote Ollama server via its native API:

    POST /api/chat   — chat completion (supports ``stream: true``)
    GET  /api/tags   — list installed models

Streaming yields plain string chunks (delta text) so callers can forward
them over SSE/WebSocket without caring about Ollama's wire format.
"""

import json
from typing import Any, Dict, Generator, List, Optional

import requests

from django.conf import settings

from libs.ai.errors import AIServiceError, AIServiceTimeout, AIServiceUnavailable

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma4:latest"
DEFAULT_TIMEOUT = 300  # seconds — cold model load can take >60s


class OllamaClient:
    """Thin HTTP client around an Ollama server.

    Usage::

        client = OllamaClient()
        reply = client.chat([{"role": "user", "content": "hi"}])

        for chunk in client.chat_stream(messages):
            print(chunk, end="", flush=True)
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        keep_alive: Optional[str] = None,
    ):
        self.base_url = (base_url or getattr(settings, "OLLAMA_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.model = model or getattr(settings, "OLLAMA_MODEL", DEFAULT_MODEL)
        self.timeout = timeout or getattr(settings, "OLLAMA_TIMEOUT", DEFAULT_TIMEOUT)
        # keep_alive controls how long the model stays loaded in memory
        # (e.g. "30m", "-1" = forever). Avoids the 60-90s cold load per call.
        self.keep_alive = keep_alive or getattr(settings, "OLLAMA_KEEP_ALIVE", "30m")

    # ------------------------------------------------------------------
    # Request helper
    # ------------------------------------------------------------------

    def _post(self, path: str, payload: Dict[str, Any], stream: bool = False):
        url = f"{self.base_url}{path}"
        try:
            return requests.post(url, json=payload, stream=stream, timeout=self.timeout)
        except requests.exceptions.Timeout as exc:
            raise AIServiceTimeout(f"Ollama timed out after {self.timeout}s: {url}") from exc
        except requests.exceptions.ConnectionError as exc:
            raise AIServiceUnavailable(f"Cannot reach Ollama at {self.base_url}") from exc
        except requests.exceptions.RequestException as exc:
            raise AIServiceError(f"Ollama request failed: {exc}") from exc

    @staticmethod
    def _raise_for_error(response) -> None:
        if response.ok:
            return
        try:
            detail = response.json().get("error", response.text)
        except ValueError:
            detail = response.text
        raise AIServiceError(f"Ollama returned HTTP {response.status_code}: {detail}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Quick liveness probe against the Ollama server."""
        try:
            requests.get(f"{self.base_url}/api/version", timeout=5)
            return True
        except requests.exceptions.RequestException:
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        """List installed models: [{"name", "size", ...}, ...]."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=15)
        except requests.exceptions.Timeout as exc:
            raise AIServiceTimeout("Ollama timed out on /api/tags") from exc
        except requests.exceptions.ConnectionError as exc:
            raise AIServiceUnavailable(f"Cannot reach Ollama at {self.base_url}") from exc
        self._raise_for_error(response)
        return response.json().get("models", [])

    def chat(self, messages: List[Dict[str, str]], model: Optional[str] = None,
             options: Optional[Dict[str, Any]] = None, tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """Non-streaming chat. Returns the full Ollama response
        (``{"message": {"role", "content"}, "eval_count", ...}``).

        *tools*: danh sách tool schema (native tool-calling cho model hỗ trợ).
        """
        payload = self._build_payload(messages, model, options, stream=False, tools=tools)
        response = self._post("/api/chat", payload, stream=False)
        self._raise_for_error(response)
        return response.json()

    def chat_stream_events(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Streaming chat — yield TỪNG SỰ KIỆN dạng dict, giữ nguyên tin nhắn.

        Yield: ``{"content": "<delta>", "tool_calls": [...]}``

        - ``content``   : phần text delta (có thể rỗng ở frame tool).
        - ``tool_calls``: native tool-calling của Ollama/OpenAI. Chuẩn của
          Ollama đẩy TOÀN BỘ ``tool_calls`` ở frame ``done`` cuối cùng, nên
          đây là nơi DUY NHẤT agent biết model có muốn gọi tool hay không.

        VÌ SAO KHÔNG DÙNG `chat_stream` CHO AGENT:
          `chat_stream` chỉ yield text và BỎ QUA `tool_calls` ⇒ agent không bao
          giờ biết model muốn gọi tool, mọi lượt gọi tool trở thành 1 vòng
          lãng phí. Agent dùng hàm này; luồng chat thuần vẫn dùng
          `chat_stream` (đơn giản hơn).

        Raises the same AIServiceError family as ``chat``.
        """
        payload = self._build_payload(messages, model, options, stream=True, tools=tools)
        response = self._post("/api/chat", payload, stream=True)
        self._raise_for_error(response)
        try:
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                if data.get("error"):
                    raise AIServiceError(f"Ollama stream error: {data['error']}")
                message = data.get("message") or {}
                tool_calls = message.get("tool_calls") or []
                content = message.get("content") or ""
                if content or tool_calls:
                    yield {"content": content, "tool_calls": tool_calls}
                if data.get("done"):
                    break
        except requests.exceptions.RequestException as exc:
            raise AIServiceError(f"Ollama stream interrupted: {exc}") from exc
        finally:
            response.close()

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict]] = None,
    ) -> Generator[str, None, None]:
        """Streaming chat — yields delta text chunks as they arrive.

        Raises the same AIServiceError family as ``chat``; network failures
        mid-stream surface as AIServiceError too.
        """
        for event in self.chat_stream_events(messages, model, options, tools):
            if event.get("content"):
                yield event["content"]

    def _build_payload(self, messages, model, options, stream: bool,
                       tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": stream,
            "keep_alive": self.keep_alive,
        }
        if tools:
            payload["tools"] = tools
        if options:
            payload["options"] = options
        return payload
