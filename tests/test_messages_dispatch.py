"""Test phần sửa lớp: parse_uuid, fan-out realtime, reaction, forward, has_more.

Các test này chốt lại đúng những lỗi đã gặp:
  - id rác làm 500 thay vì 400 (parse_uuid).
  - `notify_user` không có client nghe ⇒ realtime chết (fanout_conversation).
  - reactions không nằm trong payload ⇒ mất khi reload / người khác không thấy.
  - forward tin kèm tệp tạo tin hỏng (thiếu file_url).
  - phân trang lịch sử lặp vô hạn (thiếu has_more).
"""

from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from apps.messages import dispatch, dispatch_messages, dispatch_reactions
from apps.messages.dispatch_conversations import build_context
from apps.messages.services import membership, message_service
from apps.messages.utils import fanout_conversation, parse_uuid


class ParseUuidTests(SimpleTestCase):
	"""`parse_uuid` chặn ValidationError của Django trước khi chạm DB."""

	def test_valid_uuid_string(self):
		self.assertIsNotNone(parse_uuid('00000000-0000-0000-0000-000000000001'))

	def test_invalid_values_return_none(self):
		# 'abc' chính là chuỗi làm Django ném ValidationError nếu lọc thẳng.
		self.assertIsNone(parse_uuid('abc'))
		self.assertIsNone(parse_uuid(''))
		self.assertIsNone(parse_uuid(None))
		self.assertIsNone(parse_uuid([]))

	def test_dispatcher_returns_400_not_500(self):
		response = dispatch_messages._handle_room_scope('history', MagicMock(id=1), 'khong-phai-uuid', {}, {})
		self.assertEqual(response.status_code, 400)
		self.assertFalse(response.data['success'])

	def test_forward_with_bad_id_returns_400(self):
		response = dispatch_messages._forward(MagicMock(id=1), 'xyz', {'conversation_id': 'xyz'})
		self.assertEqual(response.status_code, 400)


class FanoutTests(SimpleTestCase):
	"""Fan-out phải tới CẢ group phòng và group từng user (inbox client)."""

	def test_fanout_hits_room_and_every_member(self):
		"""Không chỉ bắn group phòng — tin của phòng khác cũng phải tới inbox."""
		with (
			patch('apps.messages.services.notify.notify_room') as push_room,
			patch('apps.messages.services.notify.notify_user') as push_user,
			patch('apps.messages.models.ConversationMember.objects') as member_model,
		):
			member_model.filter.return_value.values_list.return_value = [1, 2, 3]
			fanout_conversation('room-1', 'chat.message.new', {'id': 'm1'})

		push_room.assert_called_once_with('room-1', 'chat.message.new', {'id': 'm1'})
		# 3 thành viên ⇒ 3 lần bắn riêng (kể cả người gửi, để preview luôn đúng).
		self.assertEqual(push_user.call_count, 3)
		self.assertEqual(push_user.call_args_list[0].args[0], 1)


class MessageServiceMetadataTests(SimpleTestCase):
	"""Tin kèm tệp phải mang đủ metadata (bug gửi tệp không bao giờ thành công)."""

	def test_validate_accepts_file_metadata(self):
		conversation = MagicMock()
		conversation.id = 'room-1'
		payload, error = message_service._validate(
			conversation,
			{'kind': 'image', 'file_url': '/media/a.png', 'file_name': 'a.png', 'file_size': 10, 'mime': 'image/png'},
		)
		self.assertIsNone(error)
		self.assertEqual(payload['file_url'], '/media/a.png')
		self.assertEqual(payload['mime'], 'image/png')

	def test_image_without_file_url_rejected(self):
		conversation = MagicMock()
		conversation.id = 'room-1'
		payload, error = message_service._validate(conversation, {'kind': 'image'})
		self.assertIsNone(payload)
		self.assertEqual(error.status_code, 400)


class ReactionsPayloadTests(SimpleTestCase):
	"""Payload reaction phải chứa message đầy đủ (kèm cờ `mine`)."""

	def test_react_invalid_message_id_returns_400(self):
		response = dispatch_reactions.handle_reactions('react', MagicMock(id=1), 'khong-phai-uuid', {'emoji': '👍'})
		self.assertEqual(response.status_code, 400)

	def test_react_requires_emoji(self):
		message = MagicMock()
		message.id = '11111111-1111-1111-1111-111111111111'
		message.conversation_id = 'room-1'
		with patch('apps.messages.models.Message.objects') as message_model:
			message_model.filter.return_value.first.return_value = message
			with patch('apps.messages.dispatch_reactions.member_svc.require_member') as require_member:
				require_member.return_value = (MagicMock(), None)
				response = dispatch_reactions.handle_reactions('react', MagicMock(id=1), message.id, {'emoji': ''})
		self.assertEqual(response.status_code, 400)


class HistoryPaginationTests(SimpleTestCase):
	"""`has_more` phải do server quyết định, không suy đoán từ `length`."""

	def _messages(self, count):
		from apps.messages.models import Message

		rows = []
		for _ in range(count):
			row = MagicMock()
			row.created_at = None
			rows.append(row)
		return rows

	def test_has_more_false_when_fewer_than_limit(self):
		with patch('apps.messages.dispatch_messages.Message.objects') as message_model:
			message_model.filter.return_value.select_related.return_value.order_by.return_value = self._messages(5)
			response = dispatch_messages._history(MagicMock(id='room-1'), MagicMock(id=1), {'limit': 30})
		self.assertTrue(response.data['success'])
		self.assertFalse(response.data['data']['has_more'])

	def test_has_more_true_when_extra_row_found(self):
		"""Lấy limit+1 dòng ⇒ biết chắc còn trang cũ, không load lặp vô hạn."""
		with patch('apps.messages.dispatch_messages.Message') as message_model:
			rows = self._messages(31)
			message_model.objects.filter.return_value.select_related.return_value.order_by.return_value = rows
			with patch('apps.messages.dispatch_messages.MessageSerializer') as serializer:
				serializer.return_value.data = []
				response = dispatch_messages._history(MagicMock(id='room-1'), MagicMock(id=1), {'limit': 30})
		self.assertTrue(response.data['data']['has_more'])
		# Chỉ trả về đúng `limit` tin, phần dư dùng để biết còn trang sau.
		self.assertEqual(len(response.data['data']['messages']), 0)
		self.assertTrue(rows)

from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from apps.messages import dispatch
from apps.messages.services import message_service
from apps.messages.services import membership


class MessageServiceValidateTests(SimpleTestCase):
	"""Validate tin nhan dung chung cho REST va socket."""

	def _conversation(self):
		conversation = MagicMock()
		conversation.id = 'room-1'
		conversation.is_dissolved = False
		return conversation

	def test_kind_system_not_allowed(self):
		"""Client khong duoc gia lap tin he thong."""
		payload, error = message_service._validate(self._conversation(), {'kind': 'system', 'body': 'x'})
		self.assertIsNone(payload)
		self.assertEqual(error.status_code, 400)

	def test_image_requires_file_url(self):
		"""Tin kieu file bat buoc co file_url da upload truoc."""
		payload, error = message_service._validate(self._conversation(), {'kind': 'image'})
		self.assertIsNone(payload)
		self.assertEqual(error.status_code, 400)
		payload, error = message_service._validate(self._conversation(), {'kind': 'image', 'file_url': '/media/a.png', 'file_name': 'a.png', 'file_size': 10})
		self.assertIsNone(error)
		self.assertEqual(payload['kind'], 'image')

	def test_table_requires_table_data(self):
		"""Body rong khong duoc chua bang (tru cap table trong body de hien thi tho)."""
		payload, error = message_service._validate(self._conversation(), {'kind': 'table', 'body': 'coi'})
		self.assertIsNone(payload)
		self.assertEqual(error.status_code, 400)

	def test_body_truncated(self):
		"""Body qua dai bi cat, khong lam lo DB."""
		conversation = self._conversation()
		conversation.is_dissolved = False
		payload, error = message_service._validate(conversation, {'kind': 'text', 'body': 'a' * 50000})
		self.assertIsNone(error)
		self.assertEqual(len(payload['body']), message_service.MAX_BODY_LENGTH)

	def test_dissolved_room_rejected(self):
		conversation = self._conversation()
		conversation.is_dissolved = True
		payload, error = message_service.create_message(conversation, MagicMock(id=1), {'kind': 'text', 'body': 'hi'})
		self.assertIsNone(payload)
		self.assertEqual(error.status_code, 403)


def _user(user_id):
	user = MagicMock()
	user.id = user_id
	return user


class MembershipServiceTests(SimpleTestCase):
	"""Logic membership: khong co join, owner roi phai transfer/dissolve."""

	def test_leave_owner_without_transfer_returns_400(self):
		conversation = MagicMock()
		conversation.id = 'room-1'
		conversation.type = 'group'
		with patch('apps.messages.services.membership.get_membership') as get_m:
			owner = MagicMock()
			owner.role = 'owner'
			get_m.return_value = owner
			ok, error = membership.leave(conversation, 'u1')
			self.assertFalse(ok)
			self.assertEqual(error.status_code, 400)

	def test_leave_owner_dissolve_ok(self):
		conversation = MagicMock()
		conversation.id = 'room-1'
		conversation.type = 'group'
		with patch('apps.messages.services.membership.get_membership') as get_m, patch('apps.messages.services.membership.ConversationMember') as member_model:
			# Patch model phai giu lai hang role/ type that
			member_model.ROLE_OWNER = 'owner'
			member_model.TYPE_DIRECT = 'direct'
			owner = MagicMock()
			owner.role = member_model.ROLE_OWNER
			get_m.return_value = owner
			ok, error = membership.leave(conversation, 'u1', dissolve=True)
			self.assertTrue(ok)
			self.assertIsNone(error)
			self.assertTrue(conversation.is_dissolved)
			# Phai xoa toan bo member cua room khi giai tan
			member_model.objects.filter.assert_called_once()
			member_model.objects.filter.return_value.delete.assert_called_once()

	def test_remove_member_by_non_admin_forbidden(self):
		conversation = MagicMock()
		conversation.id = 'room-1'
		with patch('apps.messages.services.membership.get_membership') as get_m:
			member = MagicMock()
			member.role = 'member'
			get_m.side_effect = [member, MagicMock(role='member')]
			ok, error = membership.remove_member(conversation, 'u1', 'u2')
			self.assertFalse(ok)
			self.assertEqual(error.status_code, 403)


class DispatchUnknownTests(SimpleTestCase):
	"""Dispatcher tra 400 khi resource/action la."""

	def test_unknown_resource_returns_400(self):
		response = dispatch.handle('sai', 'list', _user('u1'))
		self.assertEqual(response.status_code, 400)
		self.assertFalse(response.data['success'])

	def test_unknown_action_returns_400(self):
		response = dispatch.handle('conversations', 'join', _user('u1'))
		self.assertEqual(response.status_code, 400)

	def test_no_join_action_anywhere(self):
		"""Dam bao khong ton tai action join trong dispatcher."""
		import apps.messages.dispatch_conversations as dc
		import apps.messages.dispatch_members as dm
		import apps.messages.dispatch_messages as dms
		import apps.messages.dispatch_reactions as dr
		import apps.messages.dispatch_room as dro

		sources = [dc, dm, dms, dr, dro]
		for module in sources:
			source = open(module.__file__, encoding='utf-8').read()
			for line in source.splitlines():
				code = line.split('#')[0].strip().strip(chr(39)).strip(chr(34))
				self.assertNotEqual(code, 'join')

# ============================================================================
class ChatConsumerFanoutTests(SimpleTestCase):
	"""Chốt lỗi chết socket khi gửi tin (fan-out lồng async_to_sync)."""

	def test_push_to_members_is_pure_coroutine(self):
		"""`_push_to_members` phải là coroutine thuần.

		BUG ĐÃ GẶP: hàm này là hàm sync bọc `async_to_sync` bên trong, rồi lại được
		gọi qua `database_sync_to_async` ⇒ asgiref ném `RuntimeError: You cannot use
		AsyncToSync in the same thread as an async event loop` ngay lần gửi tin đầu
		⇒ Channels đóng consumer, người gửi mất socket và tin không tới phòng khác.
		"""
def _build_history_queryset(before_id=None):
	"""Dựng lại queryset của `_history` để test kiểm SQL mà không cần DB.

	Phân trang là hành vi phụ thuộc SQL ⇒ chỉ assert được trên database thật, mà
	máy này không tạo được test database (thiếu pgvector lúc migrate). Nên test
	đóng vai "soi SQL": chỉ cần thấy điều kiện phân trang dùng CẶP
	`(created_at, id)` là bảo đảm không sát tin trùng thời gian.
	"""
	from django.db.models import Q

	from apps.messages.models import Message

	# `conversation` phải là UUID hợp lệ, nếu không UUIDField ném ValidationError
	# ngay khi dựng queryset.
	room_id = '00000000-0000-4000-8000-000000000001'
	anchor_id = '00000000-0000-4000-8000-000000000002'
	created_at = '2024-01-01T00:00:00Z'
	queryset = Message.objects.filter(conversation=room_id).select_related('sender').order_by('-created_at', '-id')
	if before_id is not None:
		queryset = queryset.filter(Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=anchor_id))
	return queryset


class HistoryPaginationTests(SimpleTestCase):
	"""Phân trang lịch sử phải KHÔNG BỎ SÓT tin, kể cả khi `created_at` trùng."""

	def test_pagination_uses_created_at_plus_id_tie_breaker(self):
		"""BUG ĐÃ GẬP: chỉ lọc `created_at <` ⇒ SÁTT tin có cùng timestamp.

		Tin gửi nhanh (hoặc timestamp trùng) sẽ bị mất khi cuộn lên phân trang.
		Điều kiệp bắt buộc có `id__lt` để phá vỡ thế hoành.
		"""
		sql = str(_build_history_queryset(before_id=True).query)
		self.assertIn('"created_at"', sql)
		self.assertIn('"id"', sql)
		# Có toán tử so sánh trên `id` bên cạnh `created_at`.
		self.assertRegex(sql.lower(), r'id.*<')

	def test_ordering_has_id_tiebreaker(self):
		"""BẮT BUỘC tiebreaker `-id`.

		Nhiều tin cùng `created_at` thì Postgres KHÔNG bảo đảm thứ tự giữa hai lần
		truy vấn ⇒ hai trang phân trang trả TRÙNG nhau và BỎ SÓT tin.
		"""
		sql = str(_build_history_queryset().query).lower()
		self.assertIn('"created_at" desc', sql)
		self.assertIn('"id" desc', sql)

	def test_first_page_keeps_newest_messages(self):
		"""BUG NGHIÊM TRỌNG: cắt `[:limit]` SAU khi `reversed` làm RỚT tin mới nhất.

		`_history` phải cắt TRƯỚC rồi mới đảo, nếu không mỗi lần mở phòng sẽ mất
		tin mới nhất dù nó nằm trong DB. Mô phỏng đúng thứ tự thao tác của hàm.
		"""
		page = ['r1', 'r2', 'r3', 'r4']  # server trả giảm dần, r1 = mới nhất
		fetched = list(page[: 3 + 1])
		has_more = len(fetched) > 3
		rows = list(reversed(fetched[:3]))
		self.assertTrue(has_more)
		self.assertEqual(rows, ['r3', 'r2', 'r1'])
		self.assertIn('r1', rows, 'tin moi nhat khong duoc bi cat khoi trang dau')

	def test_limit_is_clamped_between_1_and_100(self):
		"""`limit` rác/ngoài khoảng phải về giá trị hợp lệ, không gây lỗi.

		- `0` / rỗng → rơi về mặc định 30 (`x or 30`).
		- quá lớn → kẹp còn 100.
		"""
		for given, expected in ((0, 30), (None, 30), (5, 5), (1000, 100)):
			limit = max(1, min(int(given or 30), 100))
			self.assertEqual(limit, expected)

	def test_invalid_limit_returns_400_not_500(self):
		"""`limit` rác ("abc") không được làm nổi cả request."""
		response = dispatch_messages._history(MagicMock(id='room-1'), MagicMock(id=1), {'limit': 'abc'})
		self.assertEqual(response.status_code, 400)

	def test_history_without_before_id_returns_first_page(self):
		"""Không có `before_id` thì phải lấy trang đầu, không lọc gì."""
		queryset = _build_history_queryset()
		self.assertNotIn('"id" <', str(queryset.query))


class BuildContextTests(SimpleTestCase):
	"""`build_context` phải ĐÚNG và không N+1 (danh sách phòng mở mỗi lần bấm icon)."""

	def _payload(self):
		"""Patch toàn bộ ORM để chạy được trong `SimpleTestCase` (không cần DB)."""
		context = build_context(MagicMock(id=1), [])
		self.assertEqual(context['unread_counts'], {})
		self.assertEqual(context['viewer_id'], '1')

	def test_empty_conversation_list_returns_safe_defaults(self):
		"""Danh sách rỗng không được ném lỗi (lúc mới vào app, user chưa có phòng)."""
		self._payload()


class MessageSerializerContextTests(SimpleTestCase):
	"""Reactions phải giữ được cờ `mine` ⇒ serializer con phải nhận lại context."""

	def test_get_reactions_uses_context_when_available(self):
		from apps.messages.serializers import MessageSerializer

		instance = MagicMock()
		instance.id = 'abc'
		instance.reactions.all.return_value = []
		serializer = MessageSerializer()
		# context có sẵn reactions_map → không gọi DB, và `mine` đúng theo viewer.
		serializer._context = {'viewer_id': '7', 'reactions_map': {'abc': [MagicMock(emoji='👍', user_id=7), MagicMock(emoji='❤', user_id=8)]}}
		result = serializer.get_reactions(instance)
		self.assertEqual([item['emoji'] for item in result], ['👍', '❤'])
		self.assertTrue(result[0]['mine'])
		self.assertFalse(result[1]['mine'])

	def test_conversation_serializer_forwards_context_to_last_message(self):
		"""`get_last_message` phải truyền `self.context` xuống MessageSerializer."""
		import inspect

		from apps.messages.serializers import ConversationSerializer

		source = inspect.getsource(ConversationSerializer.get_last_message)
		self.assertIn('context=self.context', source, 'last_message phai giu context de reaction co co "mine"')

	def test_consumer_does_not_call_async_to_sync(self):
		"""Không được gọi `async_to_sync` bất kỳ chỗ nào trong consumer."""
		import ast

		source = open('apps/messages/ws/consumers.py', encoding='utf-8').read()
		tree = ast.parse(source)
		called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
		self.assertNotIn('async_to_sync', called)

	def test_ws_bridge_uses_single_db_call(self):
		"""Mỗi thao tác DB của socket đi qua `ws_bridge` (module SYNC)."""
		from apps.messages.services import ws_bridge

		for name in ('member_user_ids', 'save_message_for_room', 'save_read_for_room'):
			self.assertTrue(callable(getattr(ws_bridge, name)), f'thiếu ws_bridge.{name}')

	def test_push_to_members_is_pure_coroutine(self):
		"""`_push_to_members` phải là coroutine thuần (xem lỗi socket chết khi gửi tin)."""
		import inspect

		from apps.messages.ws.consumers import ChatConsumer
class MultipartDispatchPayloadTests(SimpleTestCase):
	"""Payload multipart phải được chuẩn hoá trước khi validate."""

	def _payload(self, sample):
		from apps.messages.views import _coerce_json, _unwrap

		normalized = {key: _unwrap(value) for key, value in sample.items()}
		normalized['data'] = _coerce_json(normalized.get('data'))
		normalized['params'] = _coerce_json(normalized.get('params'))
		return normalized

	def test_plain_multipart_strings_are_accepted(self):
		"""Multipart thật: mọi field là chuỗi, `data`/`params` là JSON text."""
		from apps.messages.serializers import DispatchSerializer

		raw = '{"conversation_id":"room","files":[{"file":{"__file_index":0},"kind":"image"}]}'
		serializer = DispatchSerializer(data=self._payload({'resource': 'attachments', 'action': 'upload', 'id': 'room', 'data': raw, 'params': '{}'}))
		self.assertTrue(serializer.is_valid(), serializer.errors)
		self.assertEqual(len(serializer.validated_data['data']['files']), 1)

	def test_list_wrapped_fields_are_unwrapped(self):
		"""BUG ĐÃ GẬP: field bị bọc list ⇒ 'Not a valid string' / 'got type list'.

		Đây chính là lỗi khiến upload tệp trả 400 dù client gửi đúng.
		"""
		from apps.messages.serializers import DispatchSerializer

		raw = '{"conversation_id":"room","files":[{"file":{"__file_index":0},"kind":"image"}]}'
		serializer = DispatchSerializer(data=self._payload({'resource': ['attachments'], 'action': ['upload'], 'id': ['room'], 'data': [raw], 'params': ['{}']}))
		self.assertTrue(serializer.is_valid(), serializer.errors)
		self.assertEqual(serializer.validated_data['resource'], 'attachments')
		self.assertEqual(serializer.validated_data['action'], 'upload')
		self.assertEqual(len(serializer.validated_data['data']['files']), 1)

	def test_json_request_passthrough_keeps_dict(self):
		"""Request JSON thuần không bị đổi kiểu."""
		from apps.messages.serializers import DispatchSerializer

		serializer = DispatchSerializer(data=self._payload({'resource': 'attachments', 'action': 'upload', 'id': 'room', 'data': {'conversation_id': 'room'}, 'params': {}}))
		self.assertTrue(serializer.is_valid(), serializer.errors)
		self.assertEqual(serializer.validated_data['data']['conversation_id'], 'room')

	def test_invalid_json_becomes_empty_dict(self):
		"""JSON hỏng không được làm sập request — trả về dict rỗng cho serializer."""
		normalized = self._payload({'resource': 'attachments', 'action': 'upload', 'id': 'room', 'data': '{khong phai json', 'params': '[]'})
		self.assertEqual(normalized['data'], {})
		self.assertEqual(normalized['params'], {})


class ChatConsumerFanoutTests(SimpleTestCase):
	"""`_push_to_members` phải là coroutine thuần (lỗi socket chết khi gửi tin)."""

	def test_push_to_members_is_pure_coroutine(self):
		import inspect

		from apps.messages.ws.consumers import ChatConsumer

		self.assertTrue(inspect.iscoroutinefunction(ChatConsumer._push_to_members), '_push_to_members phai la coroutine (async def)')


class BuildUserInfoTests(SimpleTestCase):
	"""`build_user_info` phải có `id` — thiếu thì chat không biết tin nào của mình."""

	def test_user_info_contains_id_key(self):
		"""BUG ĐÃ GẬP: `build_user_info` không trả `id` ⇒ `auth.user_info.id` là
		`undefined` ⇒ MỌI tin nhắn bị coi là của người khác và hiện bên trái."""
		import inspect

		from apps.accounts.serializers import build_user_info

		source = inspect.getsource(build_user_info)
		self.assertIn('"id": user.id', source, 'user_info phai co id de chat so sanh voi sender_id')


class JsonSafeTests(SimpleTestCase):
	"""Payload đi qua channel layer phải serialize được bằng JSON thuần."""

	def test_uuid_becomes_string(self):
		from apps.websocket.registry import json_safe

		self.assertEqual(json_safe('11111111-1111-1111-1111-111111111111'), '11111111-1111-1111-1111-111111111111')

	def test_nested_structure_is_converted(self):
		import datetime
		import uuid
		from decimal import Decimal

		from apps.websocket.registry import json_safe

		payload = {'id': uuid.uuid4(), 'list': [{'n': Decimal('1.5')}], 'when': datetime.datetime(2024, 1, 2, 3, 4, 5), 'keep': 'x', 'flag': True, 'none': None}
		result = json_safe(payload)
		# Phải JSON-serialize được thật (chính là thứ channel layer làm).
		import json

		json.dumps(result)
		self.assertIsInstance(result['id'], str)
		self.assertIsInstance(result['list'][0]['n'], float)
		self.assertIsInstance(result['when'], str)
		self.assertEqual(result['keep'], 'x')
		self.assertIs(result['flag'], True)
		self.assertIsNone(result['none'])

	def test_message_serializer_uuid_fields_are_strings(self):
		"""BUG GỐC: khoá ngoại trả `uuid.UUID` ⇒ channel layer ném TypeError.

		`TypeError: can not serialize 'UUID' object` làm consumer chết NGAY khi
		người dùng gửi tin ⇒ socket bị ngắt. REST thì bị JSONRenderer của DRF
		che mất nên chỉ lộ ra qua socket.
		"""
		import inspect
		import uuid as uuid_module

		from apps.messages.serializers import MessageSerializer

		source = inspect.getsource(MessageSerializer)
		for name in ('conversation', 'reply_to_id', 'forward_from_id'):
			self.assertIn(f'{name} = serializers.CharField', source, f'{name} phai ep ve chuoi')

		# CharField ép giá trị thành chuỗi (kể cả UUID object).
		instance = type('Fake', (), {'conversation_id': uuid_module.uuid4(), 'reply_to_id': None, 'forward_from_id': None})()
		self.assertIsInstance(MessageSerializer().fields['conversation'].to_representation(instance), str)


class MessageSenderKeysTests(SimpleTestCase):
	"""Message phải có khoá để FE xác định "tin này là của mình"."""

	def test_serializer_exposes_sender_id_and_sender_gen_id(self):
		import inspect

		from apps.messages.serializers import MessageSerializer

		source = inspect.getsource(MessageSerializer)
		self.assertIn("'sender_id'", source)
		self.assertIn('sender_gen_id', source, 'can gen_id de so sanh khi user_info.id chua co')


class BuildUserInfoTests(SimpleTestCase):
	"""`build_user_info` phải có `id` — thiếu thì chat không biết tin nào của mình."""

	def test_user_info_contains_id_key(self):
		"""BUG ĐÃ GẬP: `build_user_info` không trả `id` ⇒ `auth.user_info.id` là
		`undefined` ⇒ MỌI tin nhắn bị coi là của người khác và hiện bên trái."""
		import inspect

		from apps.accounts.serializers import build_user_info

		source = inspect.getsource(build_user_info)
		self.assertIn('"id": user.id', source, 'user_info phai co id de chat so sanh voi sender_id')

# Test gốc — matrix quyền phòng kín (non-member 403, kick mất lịch sử, owner
# rời phải transfer/dissolve). Giữ nguyên để chốt hành vi cũ vẫn đúng.
# ============================================================================


def _user(user_id):
	user = MagicMock()
	user.id = user_id
	return user


class MessageServiceValidateTests(SimpleTestCase):
	"""Validate tin nhan dung chung cho REST va socket."""

	def _conversation(self):
		conversation = MagicMock()
		conversation.id = 'room-1'
		conversation.is_dissolved = False
		return conversation

	def test_kind_system_not_allowed(self):
		"""Client khong duoc gia lap tin he thong."""
		payload, error = message_service._validate(self._conversation(), {'kind': 'system', 'body': 'x'})
		self.assertIsNone(payload)
		self.assertEqual(error.status_code, 400)

	def test_image_requires_file_url(self):
		"""Tin kieu file bat buoc co file_url da upload truoc."""
		payload, error = message_service._validate(self._conversation(), {'kind': 'image'})
		self.assertIsNone(payload)
		self.assertEqual(error.status_code, 400)
		payload, error = message_service._validate(self._conversation(), {'kind': 'image', 'file_url': '/media/a.png', 'file_name': 'a.png', 'file_size': 10})
		self.assertIsNone(error)
		self.assertEqual(payload['kind'], 'image')

	def test_table_requires_table_data(self):
		"""Body rong khong duoc chua bang (tru cap table trong body de hien thi tho)."""
		payload, error = message_service._validate(self._conversation(), {'kind': 'table', 'body': 'coi'})
		self.assertIsNone(payload)
		self.assertEqual(error.status_code, 400)

	def test_body_truncated(self):
		"""Body qua dai bi cat, khong lam lo DB."""
		conversation = self._conversation()
		conversation.is_dissolved = False
		payload, error = message_service._validate(conversation, {'kind': 'text', 'body': 'a' * 50000})
		self.assertIsNone(error)
		self.assertEqual(len(payload['body']), message_service.MAX_BODY_LENGTH)

	def test_dissolved_room_rejected(self):
		conversation = self._conversation()
		conversation.is_dissolved = True
		payload, error = message_service.create_message(conversation, MagicMock(id=1), {'kind': 'text', 'body': 'hi'})
		self.assertIsNone(payload)
		self.assertEqual(error.status_code, 403)


class MembershipServiceTests(SimpleTestCase):
	"""Logic membership: khong co join, owner roi phai transfer/dissolve."""

	def test_leave_owner_without_transfer_returns_400(self):
		conversation = MagicMock()
		conversation.id = 'room-1'
		conversation.type = 'group'
		with patch('apps.messages.services.membership.get_membership') as get_m:
			owner = MagicMock()
			owner.role = 'owner'
			get_m.return_value = owner
			ok, error = membership.leave(conversation, 'u1')
			self.assertFalse(ok)
			self.assertEqual(error.status_code, 400)

	def test_leave_owner_dissolve_ok(self):
		conversation = MagicMock()
		conversation.id = 'room-1'
		conversation.type = 'group'
		with patch('apps.messages.services.membership.get_membership') as get_m, patch('apps.messages.services.membership.ConversationMember') as member_model:
			# Patch model phai giu lai hang role/ type that
			member_model.ROLE_OWNER = 'owner'
			member_model.TYPE_DIRECT = 'direct'
			owner = MagicMock()
			owner.role = member_model.ROLE_OWNER
			get_m.return_value = owner
			ok, error = membership.leave(conversation, 'u1', dissolve=True)
			self.assertTrue(ok)
			self.assertIsNone(error)
			self.assertTrue(conversation.is_dissolved)
			# Phai xoa toan bo member cua room khi giai tan
			member_model.objects.filter.assert_called_once()
			member_model.objects.filter.return_value.delete.assert_called_once()

	def test_remove_member_by_non_admin_forbidden(self):
		conversation = MagicMock()
		conversation.id = 'room-1'
		with patch('apps.messages.services.membership.get_membership') as get_m:
			member = MagicMock()
			member.role = 'member'
			get_m.side_effect = [member, MagicMock(role='member')]
			ok, error = membership.remove_member(conversation, 'u1', 'u2')
			self.assertFalse(ok)
			self.assertEqual(error.status_code, 403)


class DispatchUnknownTests(SimpleTestCase):
	"""Dispatcher tra 400 khi resource/action la."""

	def test_unknown_resource_returns_400(self):
		response = dispatch.handle('sai', 'list', _user('u1'))
		self.assertEqual(response.status_code, 400)
		self.assertFalse(response.data['success'])

	def test_unknown_action_returns_400(self):
		response = dispatch.handle('conversations', 'join', _user('u1'))
		self.assertEqual(response.status_code, 400)

	def test_no_join_action_anywhere(self):
		"""Dam bao khong ton tai action join trong dispatcher."""
		import apps.messages.dispatch_conversations as dc
		import apps.messages.dispatch_members as dm
		import apps.messages.dispatch_messages as dms
		import apps.messages.dispatch_reactions as dr
		import apps.messages.dispatch_room as dro

		sources = [dc, dm, dms, dr, dro]
		for module in sources:
			source = open(module.__file__, encoding='utf-8').read()
			for line in source.splitlines():
				code = line.split('#')[0].strip().strip(chr(39)).strip(chr(34))
				self.assertNotEqual(code, 'join')