"""ChatConsumer: socket room kin cua app messages.

Membership check 2 lop: connect (non-member -> close 4403) va moi message.
Tin moi duoc fan-out toi ca group phong + group `user-{id}` cua tung thuoc
phong, de client nhan realtime ke ca khi dang xem phong khac (inbox).

Moi truy van DB deu boc bang `database_sync_to_async` va goi qua
`services/ws_bridge.py` (module SYNC) — consumer khong chay truy van ORM truc
tiep. `database_sync_to_async` mac dinh `thread_sensitive=True` nen moi thao
tac DB phai CHI QUAN 1 lan trong mot `await` de tranh loi "database access
from different thread" cua Django.
"""

import logging

from channels.db import database_sync_to_async

from apps.messages.services import ws_bridge
from apps.websocket.base import CLOSE_FORBIDDEN, BaseConsumer
from apps.websocket.registry import json_safe, room_group, user_group

from . import events

logger = logging.getLogger(__name__)


class ChatConsumer(BaseConsumer):
	"""Socket 1 room chat kin: ws/chat/<uuid>/?token=..."""

	room_id = None
	group_name = None

	async def connect(self):
		if not await self.check_auth():
			return
		self.room_id = self.scope['url_route']['kwargs']['room_id']
		allowed = await database_sync_to_async(self._check_member)()
		if not allowed:
			await self.close(code=CLOSE_FORBIDDEN)
			return
		self.group_name = room_group(self.room_id)
		await self.channel_layer.group_add(self.group_name, self.channel_name)
		await self.accept()

	async def disconnect(self, close_code):
		if self.group_name:
			await self.channel_layer.group_discard(self.group_name, self.channel_name)

	async def _broadcast(self, event, data, request_id=''):
		"""Ban 1 event cho moi client dang mo socket cua phong nay."""
		await self.channel_layer.group_send(self.group_name, {'type': 'fan.out', 'event': event, 'data': json_safe(data), 'request_id': request_id})

	async def handle_message(self, message_type: str, data: dict, request_id: str) -> None:
		allowed = await database_sync_to_async(self._check_member)()
		if not allowed:
			await self.send_error('NOT_MEMBER', 'Ban khong con trong room nay.', request_id)
			await self.close(code=CLOSE_FORBIDDEN)
			return
		if message_type == 'chat.send':
			await self._handle_send(data, request_id)
		elif message_type == 'chat.typing':
			await self._handle_typing(data, request_id)
		elif message_type == 'chat.read':
			await self._handle_read(data, request_id)
		else:
			await self.send_error('BAD_PAYLOAD', f'Unknown message type: {message_type}', request_id)

	def _check_member(self) -> bool:
		"""User con la member cua phong? False => phai dong socket.

		Bat `ValidationError` cua Django: `room_id` den tu URL cua client nen
		chuoi bat ky (VD 'abc') se lam ca ASGI app chet 500 thay vi chi dong
		rieng socket nay.
		"""
		from django.core.exceptions import ValidationError

		from apps.messages.models import ConversationMember

		user = self.scope.get('user')
		if user is None or getattr(user, 'is_anonymous', True):
			return False
		try:
			return ConversationMember.objects.filter(conversation_id=self.room_id, user_id=user.id).exists()
		except (ValidationError, ValueError, TypeError):
			return False

	async def _handle_send(self, data: dict, request_id: str) -> None:
		"""Luu tin nhan roi fan-out cho ca room + tung user thuoc phong."""
		saved = await database_sync_to_async(ws_bridge.save_message_for_room)(self.room_id, self.get_user(), data)
		if saved is None:
			await self.send_error('BAD_PAYLOAD', 'Khong giu duoc tin nhan (noi dung rong hoac phong da giai tan).', request_id)
			return
		await self._broadcast(events.CHAT_MESSAGE_NEW, saved, request_id)
		# Fan-out that bai KHONG duoc lam chet socket: loi nem ra ngoai se khien
		# Channels dong consumer => nguoi gui mat socket ngay sau khi gui tin va
		# tin khong toi nguoi nhan o phong khac.
		try:
			await self._push_to_members(saved)
		except Exception:  # noqa: BLE001 — tin da luu trong DB, fan-out la phu
			logger.exception('Fan-out chat.message.new toi inbox that bai')

	async def _push_to_members(self, payload):
		"""Ban tin nhan toi group `user-{id}` cua tung thuoc phong (inbox client).

		QUAN TRONG — goi ham nay bang `await` truc tiep. Boc `async_to_sync` ben
		trong mot thread cua `SyncToAsync` se khien asgiref nem RuntimeError
		("You cannot use AsyncToSync in the same thread as an async event loop")
		va lam consumer CHET ngay lan gui tin dau tien. Day la coroutine thuan.
		"""
		user_ids = await database_sync_to_async(ws_bridge.member_user_ids)(self.room_id)
		for user_id in user_ids:
			await self.channel_layer.group_send(user_group(user_id), {'type': 'fan.out', 'event': events.CHAT_MESSAGE_NEW, 'data': json_safe(payload), 'request_id': ''})

	async def _handle_typing(self, data: dict, request_id: str) -> None:
		"""Bao dang go — kem `conversation` de client khong phai doan phong nao."""
		user = self.get_user()
		await self._broadcast(events.CHAT_TYPING, {'conversation': str(self.room_id), 'user_id': user.id, 'is_typing': bool(data.get('is_typing', True))}, request_id)

	async def _handle_read(self, data: dict, request_id: str) -> None:
		"""Ghi nhan da doc roi bao cho phong (den `chat.read`)."""
		user = self.get_user()
		message_id = data.get('message_id')
		await database_sync_to_async(ws_bridge.save_read_for_room)(self.room_id, user, message_id)
		await self._broadcast(events.CHAT_READ, {'conversation': str(self.room_id), 'user_id': user.id, 'message_id': str(message_id or '')}, request_id)