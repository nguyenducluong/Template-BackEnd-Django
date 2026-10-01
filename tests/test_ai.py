"""
Unit tests for the AI chat endpoint and Ollama client (no real Ollama needed).

Run: python manage.py test tests.test_ai -v 2
"""
import json
from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, SimpleTestCase, override_settings

from libs.ai import AIServiceTimeout, OllamaClient
from libs.ai.errors import AIServiceUnavailable


class OllamaClientTests(SimpleTestCase):
    @override_settings(OLLAMA_BASE_URL="http://ollama.test:11434",
                       OLLAMA_MODEL="gemma4:latest",
                       OLLAMA_TIMEOUT=123,
                       OLLAMA_KEEP_ALIVE="10m")
    def test_reads_settings(self):
        client = OllamaClient()
        self.assertEqual(client.base_url, "http://ollama.test:11434")
        self.assertEqual(client.model, "gemma4:latest")
        self.assertEqual(client.timeout, 123)
        self.assertEqual(client.keep_alive, "10m")

    def test_build_payload_defaults(self):
        client = OllamaClient()
        payload = client._build_payload(
            [{"role": "user", "content": "hi"}], None, None, stream=True
        )
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["model"], client.model)
        self.assertEqual(payload["messages"], [{"role": "user", "content": "hi"}])
        self.assertIn("keep_alive", payload)

    @mock.patch("libs.ai.ollama_client.requests.get")
    def test_is_available_false_on_connection_error(self, mock_get):
        import requests as _requests

        mock_get.side_effect = _requests.exceptions.ConnectionError("boom")
        self.assertFalse(OllamaClient().is_available())

    @mock.patch("libs.ai.ollama_client.requests.get")
    def test_is_available_true(self, mock_get):
        self.assertTrue(OllamaClient().is_available())
        mock_get.assert_called_once()


@override_settings(AI_CHAT_ENABLED=True)
class AIChatViewTests(SimpleTestCase):
    """View tests patch the module-level singleton (_client) and the cached
    availability probe (_ollama_available) — no real Ollama involved."""

    def setUp(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from apps.ai.views import AIChatView

        self.factory = APIRequestFactory()
        self.force_authenticate = force_authenticate
        self.view = AIChatView.as_view()
        self.user = SimpleNamespace(
            id=1, gen_id="12345678", is_authenticated=True, is_anonymous=False
        )

    def _post(self, payload):
        # Mặc định tools=False để test luồng stream thuần (cũ); bật tools riêng cho agent tests.
        body = {**payload, "tools": payload.get("tools", False)}
        request = self.factory.post(
            "/api/v1/ai/chat/", body, content_type="application/json"
        )
        self.force_authenticate(request, user=self.user)
        return self.view(request)

    def _patch_available(self, available):
        """Patch the cached availability probe."""
        return mock.patch("apps.ai.views._ollama_available", return_value=available)

    def _patch_stream(self, return_value=None, side_effect=None):
        """Patch the singleton client's chat_stream."""
        client = mock.MagicMock()
        client.chat_stream.return_value = return_value if return_value is not None else iter([])
        if side_effect is not None:
            client.chat_stream.side_effect = side_effect
        return mock.patch("apps.ai.views._client", client)

    def test_serializer_rejects_non_user_last_message(self):
        from apps.ai.serializers import AIChatRequestSerializer

        s = AIChatRequestSerializer(
            data={"messages": [{"role": "assistant", "content": "hello"}]}
        )
        self.assertFalse(s.is_valid())

    def test_serializer_accepts_valid_messages(self):
        from apps.ai.serializers import AIChatRequestSerializer

        s = AIChatRequestSerializer(
            data={"messages": [
                {"role": "user", "content": "xin chao"},
                {"role": "assistant", "content": "chao ban"},
                {"role": "user", "content": "hoi tiep"},
            ]}
        )
        self.assertTrue(s.is_valid())

    def test_503_when_ollama_unavailable(self):
        with self._patch_available(False):
            response = self._post({"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(response.status_code, 503)

    def test_streaming_response_emits_sse_frames(self):
        # NOTE: StreamingHttpResponse is lazy — the generator runs while we
        # consume streaming_content, so it MUST happen inside the `with`
        # while the patches are active.
        with self._patch_available(True), self._patch_stream(return_value=iter(["Xin", "chào"])):
            response = self._post({"messages": [{"role": "user", "content": "hi"}]})

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "text/event-stream")
            body = b"".join(response.streaming_content).decode("utf-8")
        frames = [line for line in body.split("\n") if line.startswith("data: ")]
        self.assertEqual(
            frames,
            [
                'data: {"content": "Xin"}',
                'data: {"content": "chào"}',
                "data: [DONE]",
            ],
        )

    def test_stream_error_frame_on_timeout(self):
        with self._patch_available(True), self._patch_stream(side_effect=AIServiceTimeout("too slow")):
            response = self._post({"messages": [{"role": "user", "content": "hi"}]})
            body = b"".join(response.streaming_content).decode("utf-8")

        self.assertIn('"error"', body)
        # Terminal frame must still close the stream.
        self.assertIn("data: [DONE]", body or "")

    def test_connection_error_yields_error_frame(self):
        with self._patch_available(True), self._patch_stream(side_effect=AIServiceUnavailable("gone")):
            response = self._post({"messages": [{"role": "user", "content": "hi"}]})
            body = b"".join(response.streaming_content).decode("utf-8")

        self.assertIn('"error"', body)
        self.assertTrue(json.loads(body.splitlines()[0][len("data: "):])["error"])

    def test_availability_probe_is_cached(self):
        """Second call within TTL must NOT re-probe Ollama (cache hit)."""
        with mock.patch("apps.ai.views._client") as client, \
                mock.patch("apps.ai.views.cache") as cache_mock:
            client.is_available.return_value = True
            # 1st call: cache miss -> probe + set; 2nd call: cache hit -> skip.
            cache_mock.get.side_effect = [None, True]
            from apps.ai.views import _ollama_available

            _ollama_available()
            _ollama_available()
            self.assertEqual(client.is_available.call_count, 1)
            self.assertEqual(cache_mock.set.call_count, 1)


@override_settings(AI_CHAT_ENABLED=False)
class AIDisabledTests(SimpleTestCase):
    """Cờ AI_CHAT_ENABLED=False phải chặn CẢ chat lẫn FAQ.

    Trước đây chỉ `AIMCPService` đọc cài flag, còn endpoint chat thì không -
    đặt False vẫn chat được là bug.
    """

    def setUp(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from apps.ai.views import AIChatView, FAQListView

        self.factory = APIRequestFactory()
        self.force_authenticate = force_authenticate
        self.chat_view = AIChatView.as_view()
        self.faq_view = FAQListView.as_view()
        self.user = SimpleNamespace(
            id=1, gen_id="12345678", is_authenticated=True, is_anonymous=False
        )

    def _call(self, view, data):
        request = self.factory.post("/api/v1/ai/chat/", data, content_type="application/json")
        self.force_authenticate(request, user=self.user)
        return view(request)

    def test_chat_blocked_when_flag_off(self):
        response = self._call(
            self.chat_view,
            {"messages": [{"role": "user", "content": "hi"}]},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn("AI_CHAT_ENABLED", response.data["message"]) if hasattr(response, "data") else None

    def test_faq_blocked_when_flag_off(self):
        request = self.factory.get("/api/v1/ai/faq/")
        self.force_authenticate(request, user=self.user)
        response = self.faq_view(request)
        self.assertEqual(response.status_code, 403)

@override_settings(AI_CHAT_ENABLED=True)
class AIMetaAndMcpTests(SimpleTestCase):
    """Endpoint meta + mcp — nguồn duy nhất để FE dựng tab MCP/Form.

    Trước đây `AIMCPService` + `mcp_server.py` không nơi nào import nên tính
    năng MCP hoàn toàn không tới được HTTP.
    """

    def setUp(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from apps.ai.views import AIMCPView, AIMetaView

        self.factory = APIRequestFactory()
        self.force_authenticate = force_authenticate
        self.meta_view = AIMetaView.as_view()
        self.mcp_view = AIMCPView.as_view()
        self.user = SimpleNamespace(
            id=1, gen_id="12345678", is_authenticated=True, is_anonymous=False
        )

    def _auth(self, request):
        self.force_authenticate(request, user=self.user)
        return request

    def test_meta_reports_enabled_and_lists_tools(self):
        response = self.meta_view(self._auth(self.factory.get("/api/v1/ai/meta")))
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertTrue(data["chat_enabled"])
        self.assertGreater(len(data["tools"]), 0)
        self.assertIn("vi", data["locales"])  # nhãn đa ngôn ngữ cho FE

    def test_mcp_tools_list_returns_jsonrpc(self):
        response = self.mcp_view(
            self._auth(
                self.factory.post(
                    "/api/v1/ai/mcp",
                    {"jsonrpc": "2.0", "id": 7, "method": "tools/list"},
                    content_type="application/json",
                )
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["id"], 7)
        self.assertGreater(len(json.loads(response.content)["result"]["tools"]), 0)

    def test_mcp_missing_method_is_jsonrpc_error(self):
        response = self.mcp_view(
            self._auth(self.factory.post("/api/v1/ai/mcp", {"id": 1}, content_type="application/json"))
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["error"]["code"], -32600)

    def test_mcp_unknown_method_is_jsonrpc_error(self):
        response = self.mcp_view(
            self._auth(
                self.factory.post(
                    "/api/v1/ai/mcp",
                    {"id": 1, "method": "resources/list"},
                    content_type="application/json",
                )
            )
        )
        self.assertEqual(json.loads(response.content)["error"]["code"], -32601)

    def test_mcp_missing_tool_name_is_jsonrpc_error(self):
        response = self.mcp_view(
            self._auth(
                self.factory.post(
                    "/api/v1/ai/mcp",
                    {"id": 1, "method": "tools/call", "params": {}},
                    content_type="application/json",
                )
            )
        )
        self.assertEqual(json.loads(response.content)["error"]["code"], -32602)


class AIChatHistoryTests(SimpleTestCase):
    """Lịch sử chat + RAG — chỉ kiểm phần LOGIC, không đụng DB thật.

    SimpleTestCase cấm truy vấn DB nên mọi thao tác ghi/đọc bị chặn. Đây cũng
    là lý do lưu lịch sử phải TÙY CHỌN: chat không có session_id thì không
    chạm DB, nên vẫn chạy được kể cả khi bảng lịch sử chưa sẵn sàng.
"""

    def setUp(self):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from apps.ai.views import AIChatView

        self.factory = APIRequestFactory()
        self.force_authenticate = force_authenticate
        self.view = AIChatView.as_view()
        self.user = SimpleNamespace(
            id=1, gen_id="12345678", is_authenticated=True, is_anonymous=False
        )

    def _chat(self, payload, chunks=["Ok"]):
        client = mock.MagicMock()
        client.chat_stream.return_value = iter(chunks)
        request = self.factory.post("/api/v1/ai/chat", payload, content_type="application/json")
        self.force_authenticate(request, user=self.user)
        with mock.patch("apps.ai.views._client", client), \
                mock.patch("apps.ai.views._ollama_available", return_value=True):
            response = self.view(request)
            body = b"".join(response.streaming_content).decode("utf-8")
        return response, body

    @override_settings(AI_CHAT_ENABLED=True)
    def test_chat_without_session_id_touches_no_db(self):
        # Không gửi session_id => không ghi lịch sử (và không cần bảng lịch sử).
        response, body = self._chat(
            {"messages": [{"role": "user", "content": "chào"}], "tools": False}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-Chat-Session-Id", response)

    @override_settings(AI_CHAT_ENABLED=True)
    def test_bad_session_id_does_not_error(self):
        # session_id không tồn tại => bỏ qua lưu lịch sử, KHÔNG ném lỗi.
        response, _ = self._chat(
            {
                "messages": [{"role": "user", "content": "chào"}],
                "tools": False,
                "session_id": "00000000-0000-0000-0000-000000000000",
            }
        )
        self.assertEqual(response.status_code, 200)


class AIRagDegradationTests(SimpleTestCase):
    """RAG phải SỤY GIẢM ÊM, tuyệt đối không làm hỏng chat."""

    def test_build_context_returns_empty_when_no_embedding(self):
        from apps.ai import rag

        with mock.patch("apps.ai.rag.embed_one", return_value=None):
            self.assertEqual(rag.build_context(object(), "câu hỏi"), [])

    def test_build_context_swallows_embed_exception(self):
        from apps.ai import rag

        with mock.patch("apps.ai.rag.embed_one", side_effect=RuntimeError("ollama chết")):
            self.assertEqual(rag.build_context(object(), "câu hỏi"), [])

    def test_save_message_handles_no_embedding(self):
        from apps.ai import rag

        self.assertIsNone(rag.save_message(object(), None, "user", "   "))


class AISseTerminalFrameTests(SimpleTestCase):
    """Frame [DONE] phải được phát ở MỌI nhánh kết thúc, kể cả lỗi."""

    def _run(self, side_effect, chunks=["x"]):
        from rest_framework.test import APIRequestFactory, force_authenticate

        from apps.ai.views import AIChatView

        client = mock.MagicMock()
        if isinstance(side_effect, Exception):
            client.chat_stream.side_effect = side_effect
        else:
            client.chat_stream.return_value = iter(chunks)
        request = APIRequestFactory().post(
            "/api/v1/ai/chat",
            {"messages": [{"role": "user", "content": "chào"}], "tools": False},
            content_type="application/json",
        )
        force_authenticate(request, user=SimpleNamespace(id=1, is_authenticated=True, is_anonymous=False))
        with mock.patch("apps.ai.views._client", client), \
                mock.patch("apps.ai.views._ollama_available", return_value=True):
            response = AIChatView.as_view()(request)
            return b"".join(response.streaming_content).decode("utf-8")

    def test_done_frame_on_success(self):
        self.assertIn("data: [DONE]", self._run(None, ["a", "b"]))

    def test_done_frame_on_timeout(self):
        from libs.ai import AIServiceTimeout

        body = self._run(AIServiceTimeout("too slow"))
        self.assertIn("error", body)
        self.assertIn("data: [DONE]", body)

    def test_done_frame_on_unavailable(self):
        from libs.ai import AIServiceUnavailable

        body = self._run(AIServiceUnavailable("backend chết"))
        self.assertIn("error", body)
        self.assertIn("data: [DONE]", body)

