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
        request = self.factory.post(
            "/api/v1/ai/chat/", payload, content_type="application/json"
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
