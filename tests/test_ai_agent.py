"""
Unit tests cho ToolAgent (tool-calling) — không cần DB thật.

Run: python manage.py test tests.test_ai_agent -v 2
"""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.ai.agent import ToolAgent
from apps.ai.tools.base import ToolSpec


def _fake_client():
    client = mock.MagicMock()
    return client


def _tool_result(text):
    return {"content": [{"type": "text", "text": text}]}


def _chat_reply(content, tool_calls=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"message": msg}


class ParseJsonCallTests(SimpleTestCase):
    def test_plain_json(self):
        r = ToolAgent._parse_json_call('{"tool": "user.get_by_gen_id", "args": {"gen_id": "00000001"}}')
        self.assertEqual(r, {"tool": "user.get_by_gen_id", "args": {"gen_id": "00000001"}})

    def test_with_code_fence(self):
        r = ToolAgent._parse_json_call('```json\n{"tool": "info.orgs"}\n```')
        self.assertEqual(r, {"tool": "info.orgs", "args": {}})

    def test_json_embedded_in_text(self):
        r = ToolAgent._parse_json_call('Dữ liệu: {"tool": "system.health", "args": {}}')
        self.assertEqual(r, {"tool": "system.health", "args": {}})

    def test_not_a_tool_call(self):
        self.assertIsNone(ToolAgent._parse_json_call("Xin chào, hôm nay thế nào?"))

    def test_unknown_tool_rejected(self):
        self.assertIsNone(ToolAgent._parse_json_call('{"tool": "nonexistent", "args": {}}'))


class ToolAgentJsonFallbackTests(SimpleTestCase):
    def test_calls_tool_then_summarizes(self):
        client = _fake_client()
        client.chat.side_effect = [
            _chat_reply('{"tool": "user.get_by_gen_id", "args": {"gen_id": "00000007"}}'),
            _chat_reply("User #7: Nguyễn Đức Lương"),
        ]
        user = SimpleNamespace(id=1, org_id=2)

        with mock.patch("apps.ai.agent.execute_tool", return_value=_tool_result("[DATA]")) as ex:
            text = ToolAgent(client=client, max_turns=3).run(
                [{"role": "user", "content": "Ai là user 7?"}], user=user
            )

        self.assertEqual(text, "User #7: Nguyễn Đức Lương")
        ex.assert_called_once_with("user.get_by_gen_id", user, {"gen_id": "00000007"})

        # Lượt 2 phải có tin nhắn role "tool" chứa kết quả.
        second_messages = client.chat.call_args_list[1][0][0]
        tool_msg = [m for m in second_messages if m["role"] == "tool"]
        self.assertTrue(tool_msg)
        self.assertIn("[DATA]", tool_msg[0]["content"])

    def test_permission_denied_no_loop(self):
        client = _fake_client()
        client.chat.side_effect = [
            _chat_reply('{"tool": "user.get_by_gen_id", "args": {}}'),
            _chat_reply("xong"),
        ]
        with mock.patch("apps.ai.agent.execute_tool", return_value={
            "isError": True,
            "content": [{"type": "text", "text": "Không có quyền"}],
        }):
            text = ToolAgent(client=client, max_turns=3).run([])
        self.assertEqual(text, "xong")


class ToolAgentNativeTests(SimpleTestCase):
    def test_native_tool_calls_executed(self):
        client = _fake_client()
        client.chat.side_effect = [
            _chat_reply("", tool_calls=[{
                "function": {"name": "info.orgs", "arguments": {"level": 1}},
            }]),
            _chat_reply("Có 3 tổ chức cấp Group."),
        ]
        with mock.patch("apps.ai.agent.execute_tool", return_value=_tool_result("3 orgs")) as ex:
            text = ToolAgent(client=client, max_turns=3, use_native_tools=True).run(
                [{"role": "user", "content": "liệt kê org"}], user=SimpleNamespace(id=1)
            )
        self.assertEqual(text, "Có 3 tổ chức cấp Group.")
        ex.assert_called_once_with("info.orgs", mock.ANY, {"level": 1})


class ToolSpecPermissionTests(SimpleTestCase):
    def test_permission_gate(self):
        spec = ToolSpec(
            name="t", description="d",
            input_schema={"type": "object", "properties": {}},
            handler=lambda user, args: {"ok": True},
            required_powers=["write_header"],
        )
        user = SimpleNamespace(id=1, org_id=2)
        with mock.patch("apps.ai.tools.base.has_power", return_value=False):
            result = spec.call(user, {"x": 1})
        self.assertTrue(result["isError"])
        with mock.patch("apps.ai.tools.base.has_power", return_value=True):
            result = spec.call(user, {"x": 1})
        self.assertEqual(result, {"ok": True})

    def test_handler_exception_wrapped(self):
        """S3: handler raise -> tool trả error content, không để lộ exception."""
        def boom(user, args):
            raise RuntimeError("secret detail")

        spec = ToolSpec(
            name="boom", description="d",
            input_schema={"type": "object", "properties": {}},
            handler=boom,
        )
        result = spec.call(SimpleNamespace(id=1), {})
        self.assertTrue(result["isError"])
        text = result["content"][0]["text"]
        self.assertIn("boom", text)
        self.assertIn("secret detail", text)


class UserToolScopeTests(SimpleTestCase):
    """S1: user.get không expose user ngoài org / không có quyền."""

    def _user(self, uid, org):
        return SimpleNamespace(id=uid, org_id=org)

    def test_same_org_allowed(self):
        import apps.ai.tools.user_tools as ut

        caller = self._user(1, 100)
        target = self._user(2, 100)  # cùng org
        with mock.patch.object(ut, "_can_view", return_value=True), \
                mock.patch.object(ut, "has_power", return_value=False):
            # _can_view giả True -> truy cập; kiểm tra knox bị ẩn khi khác user
            row = SimpleNamespace(id=2, org_id=100, org=SimpleNamespace(name="X"),
                                  shift_id=9, shift=SimpleNamespace(shift_vi="S"),
                                  gen_id="123", full_name="A", knox_id="knox", status=1)
            data = ut._user_serialize(row, include_knox=False)
        self.assertNotIn("knox_id", data)
        self.assertEqual(data["gen_id"], "123")

    def test_cross_org_without_power_denied(self):
        from apps.ai.tools.user_tools import _can_view  # noqa: F401

        caller = self._user(1, 100)
        target = self._user(2, 200)  # khác org, khác user
        # has_power bị mock False (không có power view_profile) -> _can_view False
        with mock.patch("apps.ai.tools.user_tools.has_power", return_value=False) as hp:
            from apps.ai.tools.user_tools import _can_view as cv

            self.assertFalse(cv(caller, target))
        hp.assert_called_with(caller, ["view_profile"])


class AIChatAgentViewTests(SimpleTestCase):
    """Locked view tới agent (tools=true) qua endpoint SSE."""

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
        request = self.factory.post("/api/v1/ai/chat/", payload, content_type="application/json")
        self.force_authenticate(request, user=self.user)
        return self.view(request)

    def test_tools_true_streams_agent_text(self):
        client = mock.MagicMock()
        client.chat.return_value = {"message": {"role": "assistant", "content": "Xin chào bạn", "tool_calls": []}}
        with mock.patch("apps.ai.views._client", client), \
                mock.patch("apps.ai.views._ollama_available", return_value=True):
            response = self._post({
                "messages": [{"role": "user", "content": "chào"}],
                "tools": True,
            })
        self.assertEqual(response.status_code, 200)
        body = b"".join(response.streaming_content).decode("utf-8")
        self.assertIn("Xin chào", body)
        self.assertIn("data: [DONE]", body)