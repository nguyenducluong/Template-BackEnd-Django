"""
AI chat endpoint (streaming, SSE).

POST /api/v1/ai/chat/
    Body: {"messages": [{"role": "user", "content": "..."}, ...]}
    Resp: text/event-stream
        data: {"content": "<delta>"}      (many times)
        data: [DONE]                      (terminal frame)

GET  /api/v1/ai/faq/
    Resp: JSON envelope — danh sách FAQ active, sort theo sort_order.
GET  /api/v1/ai/meta/
    Resp: JSON envelope — chat_enabled, locales, model, tools (đã lọc quyền).
POST /api/v1/ai/mcp/
    Body: {id, method: "tools/list" | "tools/call", params}
    Resp: JSON-RPC 2.0 (luôn HTTP 200, lỗi nằm trong body.error)

Errors before streaming starts follow the standard JSON envelope
(via the custom exception handler); errors discovered mid-stream are
emitted as a final SSE error frame so the client can render them.
"""

import json
import logging

from django.core.cache import cache
from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.views import APIView

from django.http import JsonResponse, StreamingHttpResponse
from django.utils.translation import gettext as _

from libs.ai import AIServiceError, AIServiceTimeout, AIServiceUnavailable, OllamaClient
from libs.auth.throttling import ScopedRateThrottle
from libs.responses import error_response, success_response

from . import rag
from .agent import ToolAgent
from .services import get_ai_mcp_service
from .models import AIChatMessage, AIChatSession, FAQ
from .serializers import (
    AIChatMessageRowSerializer,
    AIChatRequestSerializer,
    AIChatSessionCreateSerializer,
    AIChatSessionSerializer,
    FAQSerializer,
)

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


RAG_CONTEXT_PROMPT = _(
    "Dưới đây là các lượt chat TRƯỚC đó của chính bạn (lấy theo độ liên quan). "
    "Dùng làm ngữ cảnh để trả lời nhất quán; đừng lặp lại nguyên văn, "
    "và đừng coi đây là câu hỏi mới."
)


def _resolve_session(user, session_id):
    """Phiên chat để ghi lịch sử, hoặc None nếu caller KHÔNG muốn lưu.

    Lưu lịch sử là TÙY CHỌN: chỉ bật khi FE gửi `session_id` (FE đã tự tạo
    phiên qua `POST /ai/sessions`). Không gửi ⇒ không đụng DB, giữ endpoint chat
    nhẹ và không phụ thuộc bảng lịch sử.

    `session_id` không tồn tại / thuộc người khác ⇒ None. KHÔNG tự tạo phiên mới
    ở đây: việc đó là của `POST /ai/sessions`, tránh ghi DB ẩn mỗi lượt chat.
    """
    if not session_id:
        return None
    try:
        return AIChatSession.objects.filter(id=session_id, user=user).first()
    except Exception:  # noqa: BLE001 — hỏng lịch sử không được làm hỏng chat
        logger.warning("Không đọc được phiên chat — bỏ qua lưu lịch sử")
        return None


def _save_history(user, session, text: str) -> None:
    """Lưu câu trả lời AI vào lịch sử. NUYỀN raise để hỏng lịch sử

    không kéo theo làm sập phiên chat đang stream.
    """
    text = (text or "").strip()
    if not text or session is None:
        return
    try:
        rag.save_message(user, session, AIChatMessage.ROLE_ASSISTANT, text)
        rag.touch_session(session)
    except Exception:  # noqa: BLE001
        logger.exception("Lưu lịch sử chat thất bại")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _disabled_response():
    """Cong tac AI_CHAT_ENABLED: tra None neu dang bat, tra 403 neu tat.

    Truoc day chi `AIMCPService` doc cai flag, con endpoint chat/faq thi khong -
    nghia la dat AI_CHAT_ENABLED=False van bat duoc chatbot.
    Doc qua service thay vi settings truc tiep de chi con MOT noi chua hang so.
    """
    if get_ai_mcp_service().is_enabled():
        return None
    return error_response(
        message=_("AI chatbot is disabled (AI_CHAT_ENABLED)."),
        status=status.HTTP_403_FORBIDDEN,
    )


class FAQListView(APIView):
    """GET /api/v1/ai/faq/ — danh sách câu thường hỏi (active only)."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"
    http_method_names = ["get", "options"]

    @extend_schema(
        tags=["AI"],
        responses={200: FAQSerializer(many=True)},
    )
    def get(self, request):
        disabled = _disabled_response()
        if disabled is not None:
            return disabled
        faqs = FAQ.objects.filter(is_active=True)
        serializer = FAQSerializer(faqs, many=True)
        return success_response(
            data=serializer.data,
            message=_("Success"),
        )


class AIMetaView(APIView):
    """GET /api/v1/ai/meta — cở bật/tắt, nhãn đa ngôn ngữ, danh sách tool.

    FE gọi 1 lần lúc mở dialog để biết chatbot có bật không và hiện tab MCP
    sao cho đúng quyền. Nếu AI_CHAT_ENABLED=False thì `tools` rỗng và
    `chat_enabled=false` — FE ẩn nút bot.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"
    http_method_names = ["get", "options"]

    @extend_schema(tags=["AI"], responses={200: dict})
    def get(self, request):
        data = get_ai_mcp_service().meta(request.user)
        return success_response(data=data, message=_("Success"))


class AIChatSessionListCreateView(APIView):
    """GET /api/v1/ai/sessions — lịch sử phiên (popover lịch sử ở FE).

    POST /api/v1/ai/sessions — mở phiên mới (title lấy từ câu hỏi đầu).

    LUÔN lọc `user=request.user` ở TẦNG QUERY: không phụ thuộc UI có gửi
    user_id hay không — chặn đọc lịch sử của người khác.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"
    http_method_names = ["get", "post", "options"]

    @extend_schema(tags=["AI"], responses={200: AIChatSessionSerializer(many=True)})
    def get(self, request):
        sessions = (
            AIChatSession.objects.filter(user=request.user)
            .annotate(message_count=Count("messages"))
            .order_by("-last_message_at", "-created_at")[:100]
        )
        return success_response(data=AIChatSessionSerializer(sessions, many=True).data, message=_("Success"))

    @extend_schema(tags=["AI"], request=AIChatSessionCreateSerializer, responses={201: AIChatSessionSerializer})
    def post(self, request):
        disabled = _disabled_response()
        if disabled is not None:
            return disabled
        serializer = AIChatSessionCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        session = serializer.save()
        return success_response(
            data=AIChatSessionSerializer(session).data,
            message=_("Session created"),
            status=status.HTTP_201_CREATED,
        )


class AIChatSessionMessagesView(APIView):
    """GET /api/v1/ai/sessions/<uuid>/messages — nội dung một phiên.

    `get_object_or_404(..., user=request.user)` ⇒ phiên của người khác trả 404
    chứ không rò rỉ sự tồn tại.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"
    http_method_names = ["get", "options"]

    @extend_schema(tags=["AI"], responses={200: AIChatMessageRowSerializer(many=True)})
    def get(self, request, session_id):
        disabled = _disabled_response()
        if disabled is not None:
            return disabled
        session = get_object_or_404(AIChatSession, id=session_id, user=request.user)
        messages = AIChatMessage.objects.filter(session=session).order_by("created_at")
        return success_response(
            data=AIChatMessageRowSerializer(messages, many=True).data,
            message=_("Success"),
        )


class AIToolFormView(APIView):
    """GET /api/v1/ai/tools/<name>/form — form động cho tab Form.

    Trả về `fields` đã chuẩn hoá từ JSON Schema (widget/label/required/enum...),
    FE chỉ map sang MUI, không phải hiểu JSON Schema.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"
    http_method_names = ["get", "options"]

    @extend_schema(tags=["AI"], responses={200: dict})
    def get(self, request, tool_name):
        disabled = _disabled_response()
        if disabled is not None:
            return disabled
        form = get_ai_mcp_service().build_form(tool_name, request.user)
        if form is None:
            return error_response(
                message=_("Tool not found or not permitted."),
                status=status.HTTP_404_NOT_FOUND,
            )
        return success_response(data=form, message=_("Success"))

class AIMCPView(APIView):
    """POST /api/v1/ai/mcp — JSON-RPC 2.0 (tools/list | tools/call).

    Dùng cho tab MCP/Form trong FE và client MCP bên ngoài. Toàn bộ logic
    (lọc quyền, kiểm cờ, validate schema) nằm trong `AIMCPService.mcp_dispatch`.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai"
    http_method_names = ["post", "options"]

    @extend_schema(tags=["AI"], request=dict, responses={200: dict})
    def post(self, request):
        disabled = _disabled_response()
        if disabled is not None:
            return disabled
        payload = request.data if isinstance(request.data, dict) else {}
        # JSON-RPC KHÔNG dùng HTTP status để báo lỗi nghiệp vụ — luôn 200,
        # phần `error` nằm trong body.
        return JsonResponse(get_ai_mcp_service().mcp_dispatch(request.user, payload), status=200)


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
        disabled = _disabled_response()
        if disabled is not None:
            return disabled
        serializer = AIChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        messages = [
            {"role": m["role"], "content": m["content"]}
            for m in serializer.validated_data["messages"]
            if m["role"] != "tool"  # S4: client không được bịa role "tool" (giả kết quả tool)
        ]
        use_tools = serializer.validated_data.get("tools", True)
        max_turns = serializer.validated_data.get("max_turns", 3)

        # Câu hỏi hiện tại (message cuối, luôn là role "user" do serializer chặn).
        question = messages[-1]["content"] if messages else ""

        # --- Lịch sử + RAG (chỉ khi FE gửi `session_id`) ---
        # Lưu câu hỏi TRƯỚC. Phần RAG bên dưới chỉ chạy khi FE gửi tin nhắn gộp
        # (≤1 tin) — nếu FE đã gửi đầy đủ lịch sử thì không cần RAG nữa.
        session = _resolve_session(request.user, serializer.validated_data.get("session_id"))
        # Không có `session` ⇒ caller không muốn lịch sử: bỏ qua RAG, chat vẫn chạy.
        context = []
        if session is not None:
            try:
                rag.save_message(request.user, session, AIChatMessage.ROLE_USER, question)
            except Exception:  # noqa: BLE001
                logger.exception("Luu cau hoi vao lich su that bai")

            # CHI lay RAG khi FE gui GOI Y (khong lich su). Neu FE da gui
            # toan bo lich su (len(messages) > 1) thi boi canh da co san trong
            # messages — chen RAG vao nua se TRUNG: du lap, phi token va co
            # the tra loi vi nhau.
            if len(messages) <= 1:
                try:
                    context = rag.build_context(request.user, question)
                except Exception:  # noqa: BLE001 - RAG phu, khong duoc lam hong chat
                    logger.exception("RAG: khong duoc context - chat khong co boi canh")
                    context = []
            if context:
                messages = [
                    {"role": "system", "content": RAG_CONTEXT_PROMPT},
                    *context,
                    *messages,
                ]

        if use_tools:
            # Agent tool-calling: cần dữ liệu thì gọi tool (non-stream), rồi
            # stream text cuối cùng. Giữ `tools: false` để dùng luồng cũ.
            try:
                agent = ToolAgent(client=_client, max_turns=max_turns)
                final_text = agent.run(messages, user=request.user)
            except AIServiceError as exc:
                logger.exception("AI agent run failed")
                return error_response(
                    message=str(exc), status=status.HTTP_502_BAD_GATEWAY,
                )

            # Luu lich su TRUOC khi stream: final_text da san co day du, nen
            # client ngat giua chung van giu duoc ca cau tra loi.
            _save_history(request.user, session, final_text)

            def agent_stream():
                for i in range(0, len(final_text), 24):
                    yield _sse({"content": final_text[i:i + 24]})
                yield "data: [DONE]\n\n"

            response = StreamingHttpResponse(
                agent_stream(), content_type="text/event-stream")
            response["Cache-Control"] = "no-cache"
            response["X-Accel-Buffering"] = "no"
            # FE gửi lại id này ở lượt sau để gom vào cùng một phiên.
            if session is not None:
                response["X-Chat-Session-Id"] = str(session.id)
            return response

        # Fail fast BEFORE starting the stream so the client receives a
        # normal 4xx/5xx envelope when the backend is down or times out.
        if not _ollama_available():
            logger.warning("AI chat: Ollama unavailable at %s", _client.base_url)
            return error_response(
                message=_("AI service is currently unavailable. Please try again later."),
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        def event_stream():
            # Gom noi dung da stream de luu vao lich su.
            buffer: list = []
            try:
                for chunk in _client.chat_stream(messages):
                    buffer.append(chunk)
                    yield _sse({"content": chunk})
                yield "data: [DONE]\n\n"
            except AIServiceTimeout:
                logger.exception("AI chat stream timed out")
                yield _sse({"error": _("AI request timed out. Please try again.")})
                yield "data: [DONE]\n\n"
            except AIServiceUnavailable:
                logger.exception("AI chat: backend went away mid-stream")
                yield _sse({"error": _("AI service is currently unavailable.")})
                yield "data: [DONE]\n\n"
            except AIServiceError as exc:
                logger.exception("AI chat stream error")
                yield _sse({"error": str(exc)})
                yield "data: [DONE]\n\n"
            finally:
                # KHONG yield trong `finally`: khi client ngat giua chung, Python
                # dong generator bang GeneratorExit va `yield` o day se nem
                # RuntimeError lam vong do that. Frame [DONE] da phat inline o cac
                # nhanh ben tren.
                _save_history(request.user, session, "".join(buffer))

        response = StreamingHttpResponse(
            event_stream(), content_type="text/event-stream"
        )
        if session is not None:
            response["X-Chat-Session-Id"] = str(session.id)
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # disable nginx response buffering
        return response
