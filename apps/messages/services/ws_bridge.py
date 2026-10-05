"""Cac ham SYNC cho WebSocket consumer (app messages).

Tach rieng khoi `ws/consumers.py` de consumer chi con code `async` — trong
Channels, moi truy van DB phai boc bang `database_sync_to_async`, nen de hết
logic DB o day gop 1 cho de kiem tra va de test.
"""

from ..models import ConversationMember
from .message_service import create_message
def member_user_ids(room_id):
	"""Danh sach `user_id` thuoc 1 phong (dung cho fan-out toi inbox)."""
	return list(ConversationMember.objects.filter(conversation_id=room_id).values_list('user_id', flat=True))


def save_message_for_room(room_id, sender, data):
	"""Ghi tin nhan cho 1 phong, tra payload (dict) hoac None.

	Ham SYNC dung chung cho consumer socket. Check membership 1 lan nua o day:
	`ChatConsumer.handle_message` da check truoc nhung giua 2 lan do user co the
	bi kick => tin phai bi tu choi.
	"""
	from django.core.exceptions import ValidationError

	from ..models import Conversation

	try:
		conversation = Conversation.objects.filter(id=room_id).first()
		if conversation is None:
			return None
		if not ConversationMember.objects.filter(conversation_id=room_id, user_id=sender.id).exists():
			return None
	except (ValidationError, ValueError, TypeError):
		return None
	payload, _error = create_message(conversation, sender, data)
	return payload


def save_read_for_room(room_id, user, message_id):
	"""Ghi nhan da doc + bump `last_read_message` (nguon cua `unread_count`).

	Phai bump o day nua (ngoai REST dispatcher) vi client chu yeu danh dau doc qua
	socket; neu chi lam o REST thi unread se khong bao gio ve 0. Monotonic: khong
	bao gio lui moc, tranh client doc tre lam unread nhay nguoc.
	"""
	from django.core.exceptions import ValidationError

	from ..models import ConversationMember, Message, MessageRead
	from ..utils import parse_uuid

	pk = parse_uuid(message_id)
	if pk is None:
		return
	try:
		message = Message.objects.filter(id=pk, conversation_id=room_id).first()
		if message is None:
			return
		MessageRead.objects.get_or_create(message_id=message.id, user=user)
		membership = ConversationMember.objects.filter(conversation_id=room_id, user_id=user.id).first()
		current = membership.last_read_message if membership else None
		if membership is not None and (current is None or current.created_at < message.created_at):
			membership.last_read_message = message
			membership.save(update_fields=['last_read_message'])
	except (ValidationError, ValueError, TypeError):
		return