"""Socket thong bao rieng - ha tang chung, KHONG chua nghiep vu chat.

Chat (room kin) nam o app `messages` (apps/messages/ws/).
"""

import json

from apps.websocket.base import BaseConsumer
from apps.websocket.registry import user_group


class NotificationConsumer(BaseConsumer):
	"""Socket thong bao rieng cua tung user (group user:{id})."""

	legacy_group_name = None
	group_name = None

	async def connect(self):
		if not await self.check_auth():
			return
		user = self.get_user()
		self.group_name = user_group(user.id)
		# Tuong thich nguoc: SocketService cu ban vao notifications_<id>.
		self.legacy_group_name = f'notifications_{user.id}'
		await self.channel_layer.group_add(self.group_name, self.channel_name)
		await self.channel_layer.group_add(self.legacy_group_name, self.channel_name)
		await self.accept()

	async def disconnect(self, close_code):
		if self.group_name:
			await self.channel_layer.group_discard(self.group_name, self.channel_name)
		if self.legacy_group_name:
			await self.channel_layer.group_discard(self.legacy_group_name, self.channel_name)

	async def handle_message(self, message_type, data, request_id):
		await self.send_error('BAD_PAYLOAD', f'Unknown message type: {message_type}', request_id)

	async def send_notification(self, event):
		"""Tuong thich voi SocketService cu (group_send type=send_notification)."""
		payload = event.get('data') or {}
		if isinstance(payload, dict) and 'type' in payload and 'data' in payload:
			await self.send_event(str(payload.get('type', '')), payload.get('data') or {})
		else:
			await self.send(text_data=json.dumps(payload))
