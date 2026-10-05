"""Logic membership room kin (app messages).

Moi check quyen room deu qua module nay (REST + socket dung chung):
	- is_member / require_member: chan non-member (403 NOT_MEMBER).
	- add_member: chi member hien tai duoc add (khong co join tu do).
	- remove_member: chi owner/admin, khong kick owner.
	- leave: member thuong roi thang; owner bat buoc transfer_to hoac dissolve.
"""

from django.utils import timezone

from libs.responses import error_response

from ..models import Conversation, ConversationMember

CODE_NOT_MEMBER = 'NOT_MEMBER'
CODE_FORBIDDEN = 'FORBIDDEN'


def is_member(conversation_id, user_id) -> bool:
	"""True neu user con la member cua room (chua kick/roi/giai tan)."""
	if not conversation_id or not user_id:
		return False
	return ConversationMember.objects.filter(conversation_id=conversation_id, user_id=user_id).exists()


def get_membership(conversation_id, user_id):
	"""Tra ve ConversationMember hoac None."""
	return ConversationMember.objects.filter(conversation_id=conversation_id, user_id=user_id).first()


def require_member(conversation_id, user_id):
	"""Tra ve (membership, None) neu hop le, nguoc lai (None, error_response 403)."""
	membership = get_membership(conversation_id, user_id)
	if membership is None:
		return None, error_response(message='NOT_MEMBER', status=403)
	return membership, None


def require_active_room(conversation):
	"""Room da giai tan thi khoa moi thao tac (trừ xem bao giai tan)."""
	if conversation is not None and getattr(conversation, 'is_dissolved', False):
		return error_response(message='ROOM_DISSOLVED', status=403)
	return None


def add_member(conversation, requester_id, target_user_id):
	"""Them member: requester phai la member hien tai. Tra ve (member, error)."""
	if get_membership(conversation.id, requester_id) is None:
		return None, error_response(message=CODE_NOT_MEMBER, status=403)
	if get_membership(conversation.id, target_user_id) is not None:
		return ConversationMember.objects.get(conversation=conversation, user_id=target_user_id), None
	if conversation.type == Conversation.TYPE_DIRECT:
		return None, error_response(message='DIRECT_ROOM_CANNOT_ADD', status=400)
	member = ConversationMember.objects.create(conversation=conversation, user_id=target_user_id, role=ConversationMember.ROLE_MEMBER)
	return member, None


def remove_member(conversation, requester_id, target_user_id):
	"""Xoa member: chi owner/admin, khong kick owner. Tra ve (True, error)."""
	requester = get_membership(conversation.id, requester_id)
	if requester is None:
		return False, error_response(message=CODE_NOT_MEMBER, status=403)
	if requester.role not in (ConversationMember.ROLE_OWNER, ConversationMember.ROLE_ADMIN):
		return False, error_response(message=CODE_FORBIDDEN, status=403)
	target = get_membership(conversation.id, target_user_id)
	if target is None:
		return False, error_response(message='TARGET_NOT_MEMBER', status=404)
	if target.role == ConversationMember.ROLE_OWNER:
		return False, error_response(message='CANNOT_REMOVE_OWNER', status=403)
	target.delete()
	return True, None


def leave(conversation, user_id, transfer_to=None, dissolve=False):
	"""Roi nhom. Owner bat buoc chon transfer_to hoac dissolve. Tra ve (ok, error)."""
	membership = get_membership(conversation.id, user_id)
	if membership is None:
		return False, error_response(message=CODE_NOT_MEMBER, status=403)
	if conversation.type == Conversation.TYPE_DIRECT:
		membership.delete()
		return True, None
	if membership.role != ConversationMember.ROLE_OWNER:
		membership.delete()
		return True, None
	# Owner roi nhom: chon 1 trong 2, khong cho roi vo chu.
	if dissolve:
		conversation.is_dissolved = True
		conversation.dissolved_at = timezone.now()
		conversation.save(update_fields=['is_dissolved', 'dissolved_at', 'updated_at'])
		ConversationMember.objects.filter(conversation=conversation).delete()
		return True, None
	if not transfer_to:
		return False, error_response(message='OWNER_MUST_TRANSFER_OR_DISSOLVE', status=400)
	new_owner = get_membership(conversation.id, transfer_to)
	if new_owner is None or str(transfer_to) == str(user_id):
		return False, error_response(message='TRANSFER_TARGET_INVALID', status=400)
	new_owner.role = ConversationMember.ROLE_OWNER
	new_owner.save(update_fields=['role'])
	membership.delete()
	return True, None
