"""Xu ly resource reactions: tha / bo icon (toggle)."""

from libs.responses import error_response, success_response

from . import services as member_svc
from .models import Message, MessageReaction
from .serializers import MessageSerializer
from .ws import events


def serialize_with_reactions(message, user_id):
	"""Serialize tin nhan KÈM reactions đầy đủ (có cờ `mine`).

	Payload trả về client phải giống hệt payload bắn qua socket, nếu không
	người vừa thả emoji sẽ thấy UI không đổi cho tới lần fan-out sau.
	"""
	return MessageSerializer(message, context={'viewer_id': user_id}).data


def handle_reactions(action, user, item_id, data):
	"""Tha icon cho tin nhan (goi lai de bo)."""
	from .utils import fanout_conversation, parse_uuid

	if action != 'react':
		return error_response(message='Unknown action.', status=400)
	message_id = parse_uuid(item_id or data.get('message_id'))
	if message_id is None:
		return error_response(message='ID_INVALID', status=400)
	message = Message.objects.filter(id=message_id).first()
	if message is None:
		return error_response(message='NOT_FOUND', status=404)
	_, error = member_svc.require_member(message.conversation_id, user.id)
	if error is not None:
		return error
	emoji = str(data.get('emoji') or '').strip()[:16]
	if not emoji:
		return error_response(message='EMOJI_REQUIRED', status=400)
	reaction = MessageReaction.objects.filter(message=message, user=user, emoji=emoji).first()
	if reaction is not None:
		reaction.delete()
		removed = True
	else:
		MessageReaction.objects.create(message=message, user=user, emoji=emoji)
		removed = False
	payload = serialize_with_reactions(message, user.id)
	fanout_conversation(message.conversation_id, events.CHAT_MESSAGE_UPDATED, payload)
	return success_response(data={'removed': removed, 'emoji': emoji, 'message': payload})
