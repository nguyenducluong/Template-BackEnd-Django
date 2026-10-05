"""Xu ly resource messages: history / send / edit / delete / forward / read."""

from libs.responses import created_response, error_response, success_response

from . import services as member_svc
from .models import Conversation, Message
from .serializers import MessageSerializer
from .services import message_service
from .ws import events


def handle_messages(action, user, item_id, data, params):
	"""Lich su, gui, sua, xoa mem, forward, danh dau doc (chi member)."""
	if action in ('history', 'send', 'read'):
		return _handle_room_scope(action, user, item_id, data, params)
	if action in ('edit', 'delete', 'forward'):
		return _handle_item_scope(action, user, item_id, data)
	return error_response(message='Unknown action.', status=400)


def _handle_room_scope(action, user, item_id, data, params):
	from .utils import parse_uuid

	conversation_id = parse_uuid(item_id or data.get('conversation_id'))
	if conversation_id is None:
		return error_response(message='ID_INVALID', status=400)
	conversation = Conversation.objects.filter(id=conversation_id).first()
	if conversation is None:
		return error_response(message='NOT_FOUND', status=404)
	_, error = member_svc.require_member(conversation.id, user.id)
	if error is not None:
		return error
	if conversation.is_dissolved:
		return error_response(message='ROOM_DISSOLVED', status=403)
	if action == 'history':
		return _history(conversation, user, params)
	if action == 'send':
		return _send(conversation, user, data)
	if action == 'read':
		return _read(conversation, user, data)
	return error_response(message='Unknown action.', status=400)


def _history(conversation, user, params):
	# `limit` do client gửi ⇒ parse trong try để chuỗi rác ("abc") trả 400 thay
	# vì làm nổi cả request.
	try:
		limit = int(params.get('limit', 30) or 30)
	except (TypeError, ValueError):
		return error_response(message='LIMIT_INVALID', status=400)
	limit = max(1, min(limit, 100))

	# BẮT BUỘC có tiebreaker `-id`: nhiều tin có cùng `created_at` thì Postgres trả
	# thứ tự KHÔNG xác định giữa 2 lần truy vấn ⇒ 2 trang phân trang có thể trả
	# TRÙNG nhau và BỎ SÓT tin. Sắp xếp phải tất định trên (created_at, id).
	queryset = Message.objects.filter(conversation=conversation).select_related('sender').order_by('-created_at', '-id')
	if params.get('before_id'):
		from .utils import parse_uuid

		anchor_id = parse_uuid(params.get('before_id'))
		# Anchor phải thuộc ĐÚNG phòng này, nếu không client có thể trỏ sang tin
		# phòng khác để tua vị trí phân trang.
		anchor = Message.objects.filter(id=anchor_id, conversation=conversation).first() if anchor_id is not None else None
		if anchor is not None:
			# BUG ĐÃ GẬP: chỉ lọc `created_at < anchor.created_at` là SÁTT tin
			# có cùng `created_at` với anchor (rất dễ xảy ra khi gửi nhanh /
			# timestamp trùng) ⇒ cuộn lên là mất tin không có lý do.
			# So sánh theo CẶP (created_at, id) để không bỏ sót.
			from django.db.models import Q

			queryset = queryset.filter(Q(created_at__lt=anchor.created_at) | Q(created_at=anchor.created_at, id__lt=anchor.id))

	# Lấy `limit + 1` để biết chắc còn trang cũ hơn không (FE không còn phải đoán
	# `length >= limit` — trường hợp đúng bằng limit sẽ bị load lặp vô hạn).
	#
	# BUG NGHIÊM TRỌNG: bản cũ làm `reversed(...)` RỒI mới `[:limit]` ⇒ cắt mất
	# đúng TIN MỚI NHẤT (`fetched` đã đảo thứ tự nên `[:limit]` lấy 3 tin cũ hơn
	# và rơi mất tin đầu tiên). Phải cắt TRƯỚC rồi mới đảo.
	fetched = list(queryset[: limit + 1])
	has_more = len(fetched) > limit
	rows = list(reversed(fetched[:limit]))
	return success_response(
		data={
			'messages': MessageSerializer(rows, many=True, context={'viewer_id': user.id}).data,
			'has_more': has_more,
		}
	)


def _send(conversation, user, data):
	"""REST fallback khi socket chua mo — logic ghi tin nam trong `message_service`."""
	from .utils import fanout_conversation

	payload, error = message_service.create_message(conversation, user, data)
	if error is not None:
		return error
	fanout_conversation(conversation.id, events.CHAT_MESSAGE_NEW, payload)
	return created_response(data=payload)


def _read(conversation, user, data):
	"""Đánh dấu đã đọc và BUMP `last_read_message` — nguồn sự thật cho unread_count.

	Monotonic: không bao giờ lùi mốc (tránh client đọc trễ làm unread nhảy ngược).
	"""
	from .models import MessageRead
	from .utils import fanout_conversation, parse_uuid

	message_id = parse_uuid(data.get('message_id'))
	if message_id is None:
		return error_response(message='ID_INVALID', status=400)
	message = Message.objects.filter(id=message_id, conversation=conversation).first()
	if message is None:
		return error_response(message='NOT_FOUND', status=404)
	MessageRead.objects.get_or_create(message_id=message.id, user=user)
	membership = member_svc.get_membership(conversation.id, user.id)
	current = membership.last_read_message if membership else None
	if current is None or current.created_at < message.created_at:
		membership.last_read_message = message
		membership.save(update_fields=['last_read_message'])
	fanout_conversation(conversation.id, events.CHAT_READ, {'user_id': user.id, 'message_id': str(message.id)})
	return success_response(data={'ok': True, 'message_id': str(message.id)})


def _handle_item_scope(action, user, item_id, data):
	from .utils import fanout_conversation, parse_uuid

	if action == 'forward':
		return _forward(user, item_id, data)
	message_id = parse_uuid(item_id)
	if message_id is None:
		return error_response(message='ID_INVALID', status=400)
	message = Message.objects.filter(id=message_id).select_related('conversation').first()
	if message is None:
		return error_response(message='NOT_FOUND', status=404)
	_, error = member_svc.require_member(message.conversation_id, user.id)
	if error is not None:
		return error
	if message.sender_id != user.id:
		return error_response(message='FORBIDDEN', status=403)
	if action == 'edit':
		body = str(data.get('body') or '').strip()
		if not body:
			return error_response(message='BODY_REQUIRED', status=400)
		message.body = body[:20000]
		message.is_edited = True
		message.save(update_fields=['body', 'is_edited', 'updated_at'])
	if action == 'delete':
		message.is_deleted = True
		message.save(update_fields=['is_deleted', 'updated_at'])
	if action in ('edit', 'delete'):
		payload = MessageSerializer(message, context={'viewer_id': user.id}).data
		fanout_conversation(message.conversation_id, events.CHAT_MESSAGE_UPDATED, payload)
		return success_response(data=payload)
	return error_response(message='Unknown action.', status=400)


def _forward(user, item_id, data):
	"""Chuyển tiếp sang room khác — phải copy ĐỦ metadata tệp.

	BUG ĐÃ GẶP: bản cũ chỉ copy `kind/body/table_data` rồi `Message.objects.create`
	trực tiếp (bypass validate) ⇒ tin ảnh/tệp được tạo với `file_url=''` ⇒ mở ra
	chỉ thấy "[Hình ảnh không còn]". Nay đi qua `message_service.create_message`
	để validate + bịt lỗi cùng một chỗ với tin gửi thường.
	"""
	from .utils import fanout_conversation, parse_uuid

	source_id = parse_uuid(item_id)
	target_id = parse_uuid(data.get('conversation_id'))
	if source_id is None or target_id is None:
		return error_response(message='ID_INVALID', status=400)
	source = Message.objects.filter(id=source_id).first()
	target = Conversation.objects.filter(id=target_id).first()
	if source is None or target is None:
		return error_response(message='NOT_FOUND', status=404)
	# Phải là member của CẢ phòng gốc (không chuyển tiếp tin của phòng mình không
	# còn quyền xem) và phòng đích.
	_, error = member_svc.require_member(source.conversation_id, user.id)
	if error is not None:
		return error
	_, error = member_svc.require_member(target.id, user.id)
	if error is not None:
		return error
	if target.is_dissolved:
		return error_response(message='ROOM_DISSOLVED', status=403)

	payload, create_error = message_service.create_message(
		target,
		user,
		{
			'kind': source.kind,
			'body': source.body,
			'table_data': source.table_data,
			'file_url': source.file_url,
			'file_name': source.file_name,
			'file_size': source.file_size,
			'mime': source.mime,
			'forward_from': source.id,
		},
	)
	if create_error is not None:
		return create_error
	fanout_conversation(target.id, events.CHAT_MESSAGE_NEW, payload)
	return created_response(data=payload)
