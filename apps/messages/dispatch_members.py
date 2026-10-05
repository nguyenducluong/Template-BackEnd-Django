"""Xu ly resource members: list / add / remove / set_role / set_favorite. KHONG co join."""

from libs.responses import created_response, deleted_response, error_response, success_response

from . import services as member_svc
from .models import Conversation, ConversationMember
from .serializers import ConversationMemberSerializer
from .ws import events


def post_system_message(conversation, body):
	"""Ghi 1 tin `kind='system'` vào phòng và bắn realtime (ai vào/ra/đổi tên).

	Tin hệ thống cho lịch sử nhóm "đọc lại được": mở app lên vẫn thấy ai đã rời
	nhóm thay vì mất trắng dấu vết.
	"""
	from .models import Message

	message = Message.objects.create(conversation=conversation, sender=None, kind=Message.KIND_SYSTEM, body=body[:500])
	conversation.save(update_fields=['updated_at'])
	from .utils import fanout_conversation

	fanout_conversation(conversation.id, events.CHAT_MESSAGE_NEW, message_payload(message))
	return message


def message_payload(message):
	"""Serialize tin cho socket (tin hệ thống không có reactions)."""
	from .serializers import MessageSerializer

	return MessageSerializer(message).data


def handle_members(action, user, item_id, data):
	"""Quan ly thanh vien room kin."""
	from .utils import fanout_conversation, parse_uuid

	conversation_id = parse_uuid(item_id or data.get('conversation_id'))
	if conversation_id is None:
		return error_response(message='ID_INVALID', status=400)
	conversation = Conversation.objects.filter(id=conversation_id).first()
	if conversation is None:
		return error_response(message='NOT_FOUND', status=404)
	if conversation.is_dissolved:
		return error_response(message='ROOM_DISSOLVED', status=403)
	from .services.notify import notify_user as notify_user_fn

	if action == 'list':
		_, error = member_svc.require_member(conversation.id, user.id)
		if error is not None:
			return error
		members = ConversationMember.objects.filter(conversation=conversation).select_related('user')
		return success_response(data=ConversationMemberSerializer(members, many=True).data)
	if action == 'set_favorite':
		# Yêu thích là tuỳ chọn RIÊNG của từng user ⇒ ai cũng tự bật/tắt được,
		# và KHÔNG ai trong phòng khác bị ảnh hưởng.
		membership = member_svc.get_membership(conversation.id, user.id)
		if membership is None:
			return error_response(message='NOT_MEMBER', status=403)
		membership.is_favorite = bool(data.get('is_favorite', True))
		membership.save(update_fields=['is_favorite'])
		return success_response(data={'conversation_id': str(conversation.id), 'is_favorite': membership.is_favorite})
	if action == 'add':
		# Ô nhập trên UI gọi là "mã người dùng" ⇒ người dùng dán `gen_id`.
		# `find_user` nhận cả `gen_id` lẫn `id` (xem dispatch_conversations).
		from .dispatch_conversations import find_user

		target = find_user(data.get('user_id'))
		if target is None:
			return error_response(message='TARGET_INVALID', status=404)
		# Ghi nhớ trạng thái TRƯỚC khi add để biết có phải thành viên mới hay không
		# (người đã có trong phòng thì không spam tin hệ thống).
		already_member = ConversationMember.objects.filter(conversation=conversation, user=target).exists()
		member, error = member_svc.add_member(conversation, user.id, target.id)
		if error is not None:
			return error
		if not already_member:
			post_system_message(conversation, f'{target.full_name} đã được thêm vào nhóm')
		fanout_conversation(conversation.id, events.MEMBER_ADDED, {'conversation_id': str(conversation.id), 'user_id': member.user_id})
		notify_user_fn(member.user_id, events.CONVERSATION_UPDATED, {'conversation_id': str(conversation.id)})
		return created_response(data=ConversationMemberSerializer(member).data)
	if action == 'remove':
		target_id = parse_uuid(data.get('user_id'))
		if target_id is None:
			return error_response(message='ID_INVALID', status=400)
		target_member = ConversationMember.objects.filter(conversation=conversation, user_id=target_id).select_related('user').first()
		ok, error = member_svc.remove_member(conversation, user.id, target_id)
		if error is not None:
			return error
		if target_member is not None:
			post_system_message(conversation, f'{target_member.user.full_name} đã bị xoá khỏi nhóm')
		fanout_conversation(conversation.id, events.MEMBER_REMOVED, {'conversation_id': str(conversation.id), 'user_id': str(target_id)})
		notify_user_fn(target_id, events.CONVERSATION_REMOVED, {'conversation_id': str(conversation.id)})
		return deleted_response(data={'conversation_id': str(conversation.id), 'user_id': str(target_id)})
	if action == 'set_role':
		requester = member_svc.get_membership(conversation.id, user.id)
		if requester is None:
			return error_response(message='NOT_MEMBER', status=403)
		if requester.role != ConversationMember.ROLE_OWNER:
			return error_response(message='FORBIDDEN', status=403)
		target_id = parse_uuid(data.get('user_id'))
		if target_id is None:
			return error_response(message='ID_INVALID', status=400)
		target = member_svc.get_membership(conversation.id, target_id)
		if target is None:
			return error_response(message='TARGET_NOT_MEMBER', status=404)
		role = str(data.get('role') or '')
		if role not in (ConversationMember.ROLE_ADMIN, ConversationMember.ROLE_MEMBER):
			return error_response(message='ROLE_INVALID', status=400)
		target.role = role
		target.save(update_fields=['role'])
		fanout_conversation(conversation.id, events.CONVERSATION_UPDATED, {'conversation_id': str(conversation.id)})
		return success_response(data=ConversationMemberSerializer(target).data)
	return error_response(message='Unknown action.', status=400)
