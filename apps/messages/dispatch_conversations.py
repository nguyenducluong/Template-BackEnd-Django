"""Xu ly resource conversations (list, retrieve, tao direct/group)."""

from apps.accounts.models import User
from django.db.models import Count, F, OuterRef, Q, Subquery
from libs.responses import created_response, error_response, success_response

from . import services as member_svc
from .models import Conversation, ConversationAlias, ConversationMember
from .serializers import ConversationMemberSerializer, ConversationSerializer
from .ws import events


def build_context(user, conversations):
	"""Gom alias + dem member + ten doi phuong (direct) + tin cuoi + unread + favorite.

	MOT context duy nhat cho `ConversationSerializer`. Các số liệu nặng (tin cuối,
	số tin chưa đọc) được gom sẵn ở đây thay vì để serializer query từng dòng
	⇒ không có N+1 khi danh sách có 50 phòng.
	"""
	from .models import Message

	ids = [str(c.id) for c in conversations]
	if not ids:
		return {'aliases': {}, 'member_counts': {}, 'partners': {}, 'last_messages': {}, 'unread_counts': {}, 'favorites': {}, 'viewer_id': str(user.id)}

	alias_rows = ConversationAlias.objects.filter(user=user, conversation_id__in=ids)
	aliases = {str(a.conversation_id): a.custom_name for a in alias_rows if a.custom_name}
	favorites = {str(m.conversation_id): True for m in ConversationMember.objects.filter(user=user, conversation_id__in=ids, is_favorite=True)}

	counts = {}
	for row in ConversationMember.objects.filter(conversation_id__in=ids).values('conversation_id'):
		key = str(row['conversation_id'])
		counts[key] = counts.get(key, 0) + 1

	partners = {}
	directs = [c for c in conversations if c.type == Conversation.TYPE_DIRECT]
	if directs:
		rows = ConversationMember.objects.filter(conversation_id__in=[c.id for c in directs]).exclude(user=user).select_related('user')
		for row in rows:
			partners.setdefault(str(row.conversation_id), getattr(row.user, 'full_name', ''))

	# Tin cuối mỗi phòng.
	#
	# BUG ĐÃ GẶP (hiệu năng): bản cũ nạp TOÀN BỆNH lịch sử của mọi phòng rồi mới
	# "giữ lại dòng đầu" — 50 phòng × 500 tin = 25.000 dòng vô ích mỗi lần mở danh
	# sách. Nay dùng Subquery lấy đúng 1 id/phòng rồi fetch 1 lần.
	annotated = Conversation.objects.filter(id__in=ids).annotate(last_id=Subquery(Message.objects.filter(conversation_id=OuterRef('id')).order_by('-created_at', '-id').values('id')[:1]))
	last_ids = [row.last_id for row in annotated if row.last_id]
	last_messages = {}
	if last_ids:
		for message in Message.objects.filter(id__in=last_ids).select_related('sender').prefetch_related('reactions'):
			last_messages[str(message.conversation_id)] = message

	# Unread = số tin tạo SAU mốc `last_read_message` của chính user (không tính
	# tin do chính mình gửi — giống Messenger).
	#
	# BUG ĐÃ GẬP (hiệu năng): bản cũ chạy 1 query `aggregate` cho TỪNG phòng ⇒
	# 50 phòng = 50 truy vấn mỗi lần mở danh sách. Nay gộp còn 1 query nhờ
	# `annotate` trên chính membership của user.
	# BUG ĐÃ GẬP (do chính bản tối ưu này): mốc đọc NULL làm phép
	# `created_at > NULL` cho NULL ⇒ điều kiện FALSE ⇒ phòng CHƯA TỪNG ĐỌC bị
	# tính nhầm là 0 tin chưa đọc (đúng ra mọi tin người khác đều chưa đọc).
	# Vì vậy phải OR thêm nhánh "chưa có mốc đọc".
	unread_counts = {key: 0 for key in ids}
	never_read = Q(last_read_message__isnull=True)
	after_anchor = Q(conversation__messages__created_at__gt=F('last_read_message__created_at'))
	from_others = Q(conversation__messages__sender__isnull=False) & ~Q(conversation__messages__sender=user)
	unread_rows = (
		ConversationMember.objects.filter(user=user, conversation_id__in=ids)
		.annotate(unread=Count('conversation__messages', filter=from_others & (after_anchor | never_read)))
		.values_list('conversation_id', 'unread')
	)
	for conversation_id, unread in unread_rows:
		unread_counts[str(conversation_id)] = unread or 0

	return {
		'aliases': aliases,
		'member_counts': counts,
		'partners': partners,
		'last_messages': last_messages,
		'unread_counts': unread_counts,
		'favorites': favorites,
		'viewer_id': str(user.id),
	}


def handle_list(user):
	"""Danh sach room cua chinh user (an room da giai tan)."""
	rows = ConversationMember.objects.filter(user=user, conversation__is_dissolved=False).select_related('conversation').order_by('-conversation__updated_at')
	conversations = [r.conversation for r in rows]
	serializer = ConversationSerializer(conversations, many=True, context=build_context(user, conversations))
	return success_response(data=serializer.data)


def handle_retrieve(user, item_id):
	"""Chi tiet 1 room (chi member duoc xem)."""
	from .utils import parse_uuid

	conversation_id = parse_uuid(item_id)
	if conversation_id is None:
		return error_response(message='ID_INVALID', status=400)
	conversation = Conversation.objects.filter(id=conversation_id).first()
	if conversation is None:
		return error_response(message='NOT_FOUND', status=404)
	membership, error = member_svc.require_member(conversation.id, user.id)
	if error is not None:
		return error
	if conversation.is_dissolved:
		return error_response(message='ROOM_DISSOLVED', status=403)
	members = ConversationMember.objects.filter(conversation=conversation).select_related('user')
	serializer = ConversationSerializer(conversation, context=build_context(user, [conversation]))
	return success_response(data={'conversation': serializer.data, 'my_role': membership.role, 'members': ConversationMemberSerializer(members, many=True).data})


def find_user(identifier):
	"""Tìm user theo `gen_id` HOẶC `id`.

	VÌ SAO CẦN CẢ HAI: `id` là BigAutoField tự tăng (1, 2, 3…) mà người dùng
	không hề biết; `gen_id` mới là mã 8 số in ra thẻ và gõ khi đăng nhập.
	Ô nhập trên UI ghi "mã người dùng" ⇒ người dùng sẽ dán `gen_id`. Nếu chỉ
	lọc theo `id` thì mọi lần gõ đều rơi vào TARGET_INVALID.
	"""
	if identifier in (None, ''):
		return None
	text = str(identifier).strip()
	user = User.objects.filter(gen_id=text).first()
	if user is not None:
		return user
	# Chỉ thử `id` khi chuỗi toàn số — `gen_id` có thể dạng số nên bị trùng.
	if text.isdigit():
		return User.objects.filter(id=int(text)).first()
	return None


def serialize_conversation(conversation, user):
	"""Serialize 1 room kèm context cho tên hiển thị / đếm thành viên.

	THIẾU `context` là bug đã gặp: `ConversationSerializer` đọc alias, tên đối
	phương và member_count từ context; không truyền thì `display_name` rơi về
	UUID và `member_count = 0` ⇒ UI hiện dòng trống, tưởng như tạo room hỏng.
	"""
	return ConversationSerializer(conversation, context=build_context(user, [conversation])).data


def handle_create_direct(user, data):
	"""Tao room 1-1 (trung cap cu thi tra ve room cu)."""
	target = find_user(data.get('user_id'))
	if target is None or str(target.id) == str(user.id):
		return error_response(message='TARGET_INVALID', status=400)
	mine = list(ConversationMember.objects.filter(user=user, conversation__type=Conversation.TYPE_DIRECT).values_list('conversation_id', flat=True))
	existing = ConversationMember.objects.filter(user=target, conversation_id__in=mine).values_list('conversation_id', flat=True).first()
	if existing:
		return success_response(data=serialize_conversation(Conversation.objects.get(id=existing), user))
	conversation = Conversation.objects.create(type=Conversation.TYPE_DIRECT, created_by=user)
	ConversationMember.objects.create(conversation=conversation, user=user, role=ConversationMember.ROLE_OWNER)
	ConversationMember.objects.create(conversation=conversation, user=target, role=ConversationMember.ROLE_OWNER)
	from .services.notify import notify_user as notify_user_fn

	# Báo cho ĐỐI PHƯƠNG biết có phòng mới (kênh user-riêng — họ chưa mở socket
	# phòng này nên không thể bắt qua group phòng).
	notify_user_fn(target.id, events.CONVERSATION_UPDATED, {'conversation_id': str(conversation.id), 'is_new': True})
	return created_response(data=serialize_conversation(conversation, user))


def handle_create_group(user, data):
	"""Tao nhom kin (nguoi tao lam owner)."""
	name = str(data.get('name_global') or '').strip()[:200]
	user_ids = data.get('user_ids') or []
	if not isinstance(user_ids, list):
		return error_response(message='USER_IDS_MUST_BE_LIST', status=400)
	conversation = Conversation.objects.create(type=Conversation.TYPE_GROUP, name_global=name, created_by=user)
	ConversationMember.objects.create(conversation=conversation, user=user, role=ConversationMember.ROLE_OWNER)
	added = []
	for identifier in user_ids[:500]:
		# `user_ids` nhận `gen_id` hoặc `id` (xem `find_user`); mã sai thì bỏ qua
		# thay vì làm hỏng cả request.
		target = find_user(identifier)
		if target is None or str(target.id) == str(user.id):
			continue
		ConversationMember.objects.get_or_create(conversation=conversation, user=target, defaults={'role': ConversationMember.ROLE_MEMBER})
		added.append(target)
	if added:
		names = ', '.join(item.full_name for item in added[:5])
		dispatch_members.post_system_message(conversation, f'{names} đã được thêm vào nhóm')
	from .services.notify import notify_users

	# Mỗi thành viên được thêm cần biết phòng mới để danh sách của họ tự cập nhật.
	notify_users([item.id for item in added], events.CONVERSATION_UPDATED, {'conversation_id': str(conversation.id), 'is_new': True})
	return created_response(data=serialize_conversation(conversation, user))
