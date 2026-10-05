"""Tao tin nhan — DUNG CHUNG cho ca 2 duong ghi (REST dispatcher va WebSocket).

Lý do tach file nay: truoc day `_send` (REST) va `_save_message` (socket) la hai
ban sao cua cung mot logic (validate kind/body, kiem room, tao Message, bump
`updated_at`) ⇒ sua mot cho la chi mot lan, va de lech nhau. Gio ca hai deu goi
`create_message()`.

Luu y thu tu: luon GHI DB truoc, da co `id` thật, roi moi fan-out socket — nen tin
nhan ma khong bao gio ton tai, va lich su doc lai tu DB luon khop voi thu client
vua nhan.
"""

from libs.responses import error_response

# Kind duoc phep gui qua socket/REST. `system` KHONG nam day — tin do he thong tao
# noi bo, client khong duoc gia lap.
ALLOWED_SEND_KINDS = ('text', 'markdown', 'table', 'image', 'file', 'audio')

MAX_BODY_LENGTH = 20000


def _validate(conversation, data):
	"""Kiem tra payload tin nhan. Tra (payload_dict, error_response|None)."""
	kind = str(data.get('kind') or 'text').strip()
	if kind not in ALLOWED_SEND_KINDS:
		return None, error_response(message='KIND_INVALID', status=400, errors={'kind': kind, 'allowed': list(ALLOWED_SEND_KINDS)})

	body = str(data.get('body') or '').strip()
	table_data = data.get('table_data')

	if kind == 'table':
		# Ban co the chi gui bang (cap `body` trong table_data de hien thi tho).
		if not isinstance(table_data, dict) or not table_data:
			return None, error_response(message='TABLE_DATA_INVALID', status=400)
	elif kind in ('image', 'file', 'audio'):
		# File dinh kem luon di kem 1 URL da upload truoc (POST messages/attachments).
		if not str(data.get('file_url') or '').strip():
			return None, error_response(message='FILE_URL_REQUIRED', status=400)
	elif not body:
		return None, error_response(message='BODY_REQUIRED', status=400)

	# Khong cho tro sang room khac: ma kiem thuoc room hien tai, khong phai room client goi.
	reply_to_id = data.get('reply_to')
	forward_from_id = data.get('forward_from')
	return (
		{
			'kind': kind,
			'body': body[:MAX_BODY_LENGTH],
			'table_data': table_data if kind == 'table' else None,
			'file_url': str(data.get('file_url') or '')[:500],
			'file_name': str(data.get('file_name') or '')[:255],
			'file_size': max(0, int(data.get('file_size') or 0)),
			'mime': str(data.get('mime') or '')[:128],
			'reply_to_id': reply_to_id,
			'forward_from_id': forward_from_id,
		},
		None,
	)


def _check_relation(message_model, conversation, payload):
	"""`reply_to` / `forward_from` phai cung thuoc room hien tai (khong lo chuyen
	tu phong ky cho sang phong khac — se lo tin o noi khong co quyen xem)."""
	for field in ('reply_to_id', 'forward_from_id'):
		related_id = payload.get(field)
		if not related_id:
			continue
		if not message_model.objects.filter(id=related_id, conversation_id=conversation.id).exists():
			return error_response(message=f'INVALID_{field.upper()}', status=400)
	return None


def create_message(conversation, sender, data):
	"""Tao 1 tin nhan. Tra (dict|None, error_response|None).

	dict = MessageSerializer(...).data — da co `id` thật de fan-out ngay.
	"""
	from ..models import Message
	from ..serializers import MessageSerializer

	if conversation is None:
		return None, error_response(message='NOT_FOUND', status=404)
	if conversation.is_dissolved:
		return None, error_response(message='ROOM_DISSOLVED', status=403)

	payload, error = _validate(conversation, data)
	if error is not None:
		return None, error
	relation_error = _check_relation(Message, conversation, payload)
	if relation_error is not None:
		return None, relation_error

	message = Message.objects.create(conversation=conversation, sender=sender, **payload)
	# Bump `updated_at` de danh sach hoi thoai sap xep theo phong vua hoat dong.
	# `save(update_fields=...)` chay lai auto_now nen updated_at tu cap nhat.
	conversation.save(update_fields=['updated_at'])
	return MessageSerializer(message, context={'viewer_id': sender.id}).data, None