"""
BaseConsumer — lớp cha cho MỌI consumer socket trong dự án.

App `websocket` chỉ cung cấp hạ tầng (envelope, auth, ping/pong, lỗi chuẩn).
Nghiệp vụ (chat, face, systems...) nằm ở app tương ứng, kế thừa lớp này.
"""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

# Mã đóng socket riêng của dự án (range 4400-4499, theo RFC 6455 private use).
# FE dựa vào code này để hiện toast đúng (vd 4403 = không phải member).
CLOSE_UNAUTHENTICATED = 4401
CLOSE_NOT_MEMBER = 4403
CLOSE_FORBIDDEN = 4403
CLOSE_NOT_FOUND = 4404


class BaseConsumer(AsyncWebsocketConsumer):
	"""Consumer cơ sở: xác thực + envelope + ping/pong + lỗi chuẩn."""

	async def __call__(self, scope, receive, send):
		"""Bọc vòng lặp dispatch để LỖI KHÔNG BAO GIỜ GIẾT SOCKET.

		`AsyncConsumer.__call__` mặc định để exception nổi lên tới ASGI server,
		nghĩa là chỉ cần MỘT payload không serialize được (ví dụ sót `uuid.UUID`)
		là socket của người dùng bị ngắt ngay — mất kết nối giữa chừng.

		Ở đây ta bắt lỗi, ghi log kèm `event` để truy vết, báo lỗi về client
		rồi TIẾP TỤC vòng lặp. Ưu tiên socket còn sống hơn là socket sạch.
		"""
		try:
			await super().__call__(scope, receive, send)
		except Exception:  # noqa: BLE001 — chính mục đích là nuốt mọi lỗi ở đây
			logger.exception('Lỗi trong consumer %s — socket được giữ mở', type(self).__name__)
			try:
				await self.send_error('INTERNAL_ERROR', 'Có lỗi xảy ra khi xử lý sự kiện, vui lòng thử lại.')
			except Exception:  # noqa: BLE001 — kết nối đã hỏng thì không gửi được nữa
				logger.exception('Không gửi được báo lỗi về client')

	# ------------------------------------------------------------------
	# Xác thực
	# ------------------------------------------------------------------

	def get_user(self):
		"""Trả về user từ scope (do JWTAuthMiddlewareStack gắn)."""
		return self.scope.get('user')

	def is_anonymous(self) -> bool:
		user = self.get_user()
		return user is None or getattr(user, 'is_anonymous', True)

	async def check_auth(self) -> bool:
		"""Chặn anonymous ngay khi connect. Trả về False nếu đã close."""
		if self.is_anonymous():
			await self.close(code=CLOSE_UNAUTHENTICATED)
			return False
		return True

	# ------------------------------------------------------------------
	# Envelope gửi đi
	# ------------------------------------------------------------------

	async def send_event(self, event: str, data=None, request_id: str = '') -> None:
		"""Bắn event chuẩn: {"type": "event", "event": ..., "data": ...}."""
		await self.send(text_data=json.dumps({'type': 'event', 'event': event, 'data': data or {}, 'request_id': request_id or ''}))

	async def send_error(self, code: str, detail: str = '', request_id: str = '') -> None:
		"""Bắn lỗi chuẩn: {"type": "error", "code": ..., "detail": ...}."""
		await self.send(text_data=json.dumps({'type': 'error', 'code': code, 'detail': detail or code, 'request_id': request_id or ''}))

	# ------------------------------------------------------------------
	# Nhận message (FE -> BE)
	# ------------------------------------------------------------------

	async def receive(self, text_data=None, bytes_data=None, **kwargs):
		payload = self._parse_json(text_data)
		if payload is None:
			await self.send_error('BAD_PAYLOAD', 'Invalid JSON')
			return
		message_type = str(payload.get('type', '') or '')
		request_id = str(payload.get('request_id', '') or '')
		data = payload.get('data') or {}
		if not hasattr(data, 'get'):
			await self.send_error('BAD_PAYLOAD', 'Field "data" must be an object.', request_id)
			return
		# Ping/pong dùng chung cho mọi consumer (giữ kết nối + đo trễ).
		if message_type in ('ping', 'chat.ping', 'notify.ping'):
			await self.send(text_data=json.dumps({'type': 'pong', 'request_id': request_id}))
			return
		await self.handle_message(message_type, data, request_id)

	async def handle_message(self, message_type: str, data: dict, request_id: str) -> None:
		"""App con override để xử lý nghiệp vụ. Mặc định báo type lạ."""
		await self.send_error('BAD_PAYLOAD', f'Unknown message type: {message_type}', request_id)

	# ------------------------------------------------------------------
	# Fan-out từ channel layer
	# ------------------------------------------------------------------

	async def fan_out(self, event: dict) -> None:
		"""Handler chung cho group_send(type='fan.out'): bắn event cho client."""
		await self.send_event(event.get('event', ''), event.get('data') or {}, event.get('request_id', ''))

	@staticmethod
	def _parse_json(text_data):
		try:
			payload = json.loads(text_data)
		except (TypeError, ValueError):
			return None
		return payload if isinstance(payload, dict) else None
