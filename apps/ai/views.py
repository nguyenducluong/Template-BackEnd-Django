"""
AI chat endpoint (streaming, SSE).

POST /api/v1/ai/chat/
    Body: {"messages": [{"role": "user", "content": "..."}, ...]}
    Resp: text/event-stream
        data: {"content": "<delta>"}      (many times)
        data: [DONE]                      (terminal frame)

Errors before streaming starts follow the standard JSON envelope
(via the custom exception handler); errors discovered mid-stream are
emitted as a final SSE error frame so the client can render them.
"""

import json
import logging

from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.views import APIView

from django.http import StreamingHttpResponse
from django.utils.translation import gettext as _

from libs.ai import AIServiceError, AIServiceTimeout, AIServiceUnavailable, OllamaClient
from libs.auth.throttling import ScopedRateThrottle

from .agent import ToolAgent
from .serializers import AIChatRequestSerializer

logger = logging.getLogger("apps")

# Module-level client: chỉ gán config một lần, tái sử dụng giữa các request.
_client = OllamaClient()

# Liveness probe được cache để không thêm 1 HTTP round-trip vào MỖI lần chat.
# Race window 10s là chấp nhận được: lỗi thật (backend chết giữa stream)
# vẫn được xử lý graceful bằng error frame trong event_stream().
AVAILABILITY_CACHE_KEY = "ai:ollama:available"
AVAILABILITY_CACHE_TTL = 10  # seconds


def _ollama_available() -> bool:
    """Cached liveness probe (10s)."""
    available = cache.get(AVAILABILITY_CACHE_KEY)
    if available is not None:
        return available
    available = _client.is_available()
    cache.set(AVAILABILITY_CACHE_KEY, available, timeout=AVAILABILITY_CACHE_TTL)
    return available


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


class AIChatView(APIView):
    """Streamed AI chat against the configured backend (Ollama)."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["AI"],
        request=AIChatRequestSerializer,
        responses={200: dict},
    )
    def post(self, request):
        serializer = AIChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in serializer.validated_data["messages"]
            if m["role"] != "tool"  # S4: client không được bịa role "tool" (giả kết quả tool)
        ]
        use_tools = serializer.validated_data.get("tools", True)
        max_turns = serializer.validated_data.get("max_turns", 3)

        if use_tools:
            # Agent tool-calling: cần dữ liệu thì gọi tool (non-stream), rồi
            # stream text cuối cùng. Giữ `tools: false` để dùng luồng cũ.
            try:
                agent = ToolAgent(client=_client, max_turns=max_turns)
                final_text = agent.run(messages, user=request.user)
            except AIServiceError as exc:
                logger.exception("AI agent run failed")
                from libs.responses import error_response

                return error_response(
                    message=str(exc), status=status.HTTP_502_BAD_GATEWAY,
                )

            def agent_stream():
                for i in range(0, len(final_text), 24):
                    yield _sse({"content": final_text[i:i + 24]})
                yield "data: [DONE]\n\n"

            response = StreamingHttpResponse(
                agent_stream(), content_type="text/event-stream")
            response["Cache-Control"] = "no-cache"
            response["X-Accel-Buffering"] = "no"
            return response

        # Fail fast BEFORE starting the stream so the client receives a
        # normal 4xx/5xx envelope when the backend is down or times out.
        if not _ollama_available():
            logger.warning("AI chat: Ollama unavailable at %s", _client.base_url)
            from libs.responses import error_response

            return error_response(
                message=_("AI service is currently unavailable. Please try again later."),
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        def event_stream():
            try:
                for chunk in _client.chat_stream(messages):
                    yield _sse({"content": chunk})
            except AIServiceTimeout:
                logger.exception("AI chat stream timed out")
                yield _sse({"error": _("AI request timed out. Please try again.")})
            except AIServiceUnavailable:
                logger.exception("AI chat: backend went away mid-stream")
                yield _sse({"error": _("AI service is currently unavailable.")})
            except AIServiceError as exc:
                logger.exception("AI chat stream error")
                yield _sse({"error": str(exc)})
            finally:
                # Terminal frame is emitted even on error so clients can
                # rely on it to close the stream deterministically.
                yield "data: [DONE]\n\n"

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # disable nginx response buffering
        return response
