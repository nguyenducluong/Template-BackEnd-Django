"""Xu ly doi ten global / avatar / alias / roi nhom (owner bat buoc transfer/dissolve)."""

from libs.responses import deleted_response, error_response, success_response

from . import services as member_svc
from .models import Conversation, ConversationAlias, ConversationMember
from .ws import events


def handle_single(action, user, item_id, data):
	"""Rename global, avatar, alias, set_favorite, leave tren 1 room."""
	from .utils import fanout_conversation, parse_uuid

	conversation_id = parse_uuid(item_id)
	if conversation_id is None:
		return error_response(message='ID_INVALID', status=400)
	conversation = Conversation.objects.filter(id=conversation_id).first()
	if conversation is None:
		return error_response(message='NOT_FOUND', status=404)
	membership, error = member_svc.require_member(conversation.id, user.id)
	if error is not None:
		return error

	if action == 'rename_global':
		if membership.role not in (ConversationMember.ROLE_OWNER, ConversationMember.ROLE_ADMIN):
			return error_response(message='FORBIDDEN', status=403)
		conversation.name_global = str(data.get('name_global') or '').strip()[:200]
		conversation.save(update_fields=['name_global', 'updated_at'])
		from .dispatch_conversations import serialize_conversation

		payload = serialize_conversation(conversation, user)
		fanout_conversation(conversation.id, events.CONVERSATION_UPDATED, {'conversation_id': str(conversation.id), 'name_global': conversation.name_global})
		return success_response(data=payload)
	if action == 'set_avatar':
		if membership.role not in (ConversationMember.ROLE_OWNER, ConversationMember.ROLE_ADMIN):
			return error_response(message='FORBIDDEN', status=403)
		conversation.avatar_url = str(data.get('avatar_url') or '')[:500]
		conversation.save(update_fields=['avatar_url', 'updated_at'])
		from .dispatch_conversations import serialize_conversation

		return success_response(data=serialize_conversation(conversation, user))
	if action == 'set_alias':
		alias, _ = ConversationAlias.objects.get_or_create(conversation=conversation, user=user)
		alias.custom_name = str(data.get('custom_name') or '').strip()[:200]
		alias.save(update_fields=['custom_name'])
		from .dispatch_conversations import serialize_conversation

		return success_response(data=serialize_conversation(conversation, user))
	if action == 'set_favorite':
		# Ghim phòng (riêng từng user) — dùng chung membership với tab "Yêu thích".
		membership.is_favorite = bool(data.get('is_favorite', True))
		membership.save(update_fields=['is_favorite'])
		return success_response(data={'conversation_id': str(conversation.id), 'is_favorite': membership.is_favorite})
	if action == 'leave':
		# Gom danh sách user TRƯỚC khi rời: sau khi rời/giải tán, membership đã bị
		# xoá nên `fanout_conversation` sẽ không tìm thấy ai để bắn event.
		target_user_ids = [str(item) for item in ConversationMember.objects.filter(conversation=conversation).values_list('user_id', flat=True)]
		from .services.notify import notify_room as notify_room_fn

		ok, leave_error = member_svc.leave(conversation, user.id, transfer_to=data.get('transfer_to'), dissolve=bool(data.get('dissolve')))
		if leave_error is not None:
			return leave_error
		if conversation.is_dissolved:
			notify_room_fn(conversation.id, events.CONVERSATION_DISSOLVED, {'conversation_id': str(conversation.id)})
		else:
			notify_room_fn(conversation.id, events.MEMBER_REMOVED, {'conversation_id': str(conversation.id), 'user_id': str(user.id)})
		# Bắn cho từng user qua kênh CÁ NHÂN (kênh duy nhất còn hoạt động sau khi
		# họ rời phòng — socket phòng của họ đã bị đóng/không còn nhận event).
		from .services.notify import notify_users

		event = events.CONVERSATION_DISSOLVED if conversation.is_dissolved else events.CONVERSATION_REMOVED
		notify_users(target_user_ids, event, {'conversation_id': str(conversation.id), 'user_id': str(user.id)})
		return deleted_response(data={'conversation_id': str(conversation.id)})
	return error_response(message='Unknown action.', status=400)
