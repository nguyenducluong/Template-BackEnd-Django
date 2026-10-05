"""Tien ich dung chung cho app messages."""

import logging

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def parse_uuid(value):
	"""Chuyen `value` (chuoi/UUID) thanh `uuid.UUID`, tra None neu khong hop le.

	VI SAO CAN HAM NAY:
	`Conversation.id` la UUIDField. Client gui `id` tuong doi tu` → gia tri
	khong phai UUID se lam Django nem `ValidationError` ("'abc' is not a valid
	UUID") ⇒ 500 cho ca request thay vi 400 ro rang.

	Moi noi can loc id phai di qua day:
	```python
	pk = parse_uuid(item_id or data.get('conversation_id'))
	if pk is None:
		return error_response(message='ID_INVALID', status=400)
	```
	"""
	import uuid as uuid_module

	if value in (None, '', []):
		return None
	if isinstance(value, uuid_module.UUID):
		return value
	try:
		return uuid_module.UUID(str(value).strip())
	except (ValidationError, ValueError, TypeError, AttributeError):
		logger.info('Bo qua id khong phai UUID: %r', value)
		return None


def fanout_conversation(conversation_id, event, data, exclude_user_ids=None):
	"""Ban 1 event chat toi TAT CA thanh vien cua room (ke ca chinh minh).

	Đây là mấu chốt để realtime đúng: FE chỉ mở socket cho phòng đang xem, nên
	nếu chỉ bắn vào group `room-{id}` thì tin nhắn của phòng KHÁC sẽ không tới.
	Bắn thêm vào group `user-{id}` của từng thành viên giúp client luôn biết
	phòng nào vừa có tin mới (dùng để tăng unread + cập nhật preview).
	"""
	from .models import ConversationMember
	from .services.notify import notify_room, notify_user

	notify_room(conversation_id, event, data)
	user_ids = ConversationMember.objects.filter(conversation_id=conversation_id).values_list('user_id', flat=True)
	for user_id in list(user_ids):
		if exclude_user_ids and str(user_id) in {str(item) for item in exclude_user_ids}:
			continue
		notify_user(user_id, event, data)