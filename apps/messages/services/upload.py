"""Upload tệp cho tin nhắn (app messages).

Quy ước FE đã có sẵn trong `STD/src/axios/axios.jsx::build_form_data`:
file được gửi ở FormData key "0","1",…, kèm metadata {__file_index, name, size, mime}.

QUY TẮC AN TOÀN (không tin dữ liệu client):
  - Dung lượng lấy từ file SERVER nhận được, không lấy metadata client.
  - Kiểu file nhận diện bằng magic bytes + phần mở rộng, không tin `content_type`.
  - Tên file lưu phải tự sinh (uuid), không dùng tên client (chống path traversal).
  - Check thuộc room phải là MEMBER hiện tại (giữ đúng quy tắc "room kín").
"""

import mimetypes
import os
import uuid

from django.conf import settings
from django.utils import timezone

from libs.responses import error_response

from .membership import get_membership, require_active_room

# Giới hạn dung lượng (byte) — chỉnh được qua settings.
MAX_IMAGE_SIZE = int(getattr(settings, 'CHAT_MAX_IMAGE_BYTES', 20 * 1024 * 1024))
MAX_FILE_SIZE = int(getattr(settings, 'CHAT_MAX_FILE_BYTES', 100 * 1024 * 1024))
MAX_FILES_PER_MESSAGE = 10

# Đuôi file hợp lệ → content-type tương ứng (dùng để chặn file nguy hiểm).
ALLOWED_IMAGE_EXT = {
	'.jpg': 'image/jpeg',
	'.jpeg': 'image/jpeg',
	'.png': 'image/png',
	'.gif': 'image/gif',
	'.webp': 'image/webp',
	'.bmp': 'image/bmp',
}
ALLOWED_FILE_EXT = {
	'.pdf': 'application/pdf',
	'.txt': 'text/plain',
	'.csv': 'text/csv',
	'.tsv': 'text/tab-separated-values',
	'.log': 'text/plain',
	'.json': 'application/json',
	'.xml': 'application/xml',
	'.sql': 'text/plain',
	'.py': 'text/x-python',
	'.xls': 'application/vnd.ms-excel',
	'.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
	'.doc': 'application/msword',
	'.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
	'.ppt': 'application/vnd.ms-powerpoint',
	'.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
	'.zip': 'application/zip',
	'.mp3': 'audio/mpeg',
	'.wav': 'audio/wav',
	'.m4a': 'audio/mp4',
	'.ogg': 'audio/ogg',
	'.mp4': 'video/mp4',
}
ALLOWED_EXT = {**ALLOWED_IMAGE_EXT, **ALLOWED_FILE_EXT}

# Magic bytes nhận diện file nhị phân thật (chống đổi đuôi .exe → .png).
_MAGIC_SIGNATURES = (
	(b'\xff\xd8\xff', 'image/jpeg'),
	(b'\x89PNG\r\n\x1a\n', 'image/png'),
	(b'GIF87a', 'image/gif'),
	(b'GIF89a', 'image/gif'),
	(b'%PDF-', 'application/pdf'),
	(b'PK\x03\x04', 'application/zip'),
	(b'OggS', 'audio/ogg'),
	(b'ID3', 'audio/mpeg'),
)

KIND_IMAGE = 'image'
KIND_FILE = 'file'
KIND_AUDIO = 'audio'


def _sniff_mime(upload):
	"""Đoán mime thật bằng magic bytes. Trả mime hoặc None (file văn bản thuần)."""
	try:
		upload.seek(0)
		head = upload.read(32)
		upload.seek(0)
	except (AttributeError, OSError):
		return None
	for signature, mime in _MAGIC_SIGNATURES:
		if head.startswith(signature):
			return mime
	# RIFF dùng chung cho wav/webp → phân biệt bằng 4 byte tiếp theo.
	if head.startswith(b'RIFF'):
		if head[8:12] == b'WEBP':
			return 'image/webp'
		if head[8:12] == b'WAVE':
			return 'audio/wav'
	return None


def _build_safe_name(uploaded_name, mime):
	"""Sinh tên lưu KHÔNG phụ thuộc tên client (chống path traversal)."""
	ext = os.path.splitext(uploaded_name or '')[1].lower()
	if ext not in ALLOWED_EXT:
		ext = mimetypes.guess_extension(mime or '') or ''
		if ext == '.jpe':
			ext = '.jpg'
		if ext not in ALLOWED_EXT:
			ext = ''
	return f'{uuid.uuid4().hex}{ext}'


def _relative_path(conversation_id, kind, safe_name):
	"""Đường dẫn lưu theo năm/tháng + room để dễ quản lý (dùng / cho storage backend)."""
	now = timezone.now()
	subdir = 'images' if kind == KIND_IMAGE else ('audio' if kind == KIND_AUDIO else 'files')
	return f'chat/{subdir}/{now:%Y/%m}/{conversation_id}/{safe_name}'


def _get_size(upload):
	"""Size đo từ file server nhận được — KHÔNG tin metadata client."""
	size = getattr(upload, 'size', None) or 0
	if size:
		return size
	try:
		upload.seek(0, os.SEEK_END)
		size = upload.tell()
		upload.seek(0)
	except (AttributeError, OSError):
		size = 0
	return size

def _normalize_kind(mime, kind_hint=''):
	"""Chọn `kind` của tin nhắn từ mime thật (client không được tự quyết)."""
	if mime and mime.startswith('image/'):
		return KIND_IMAGE
	if mime and mime.startswith('audio/'):
		return KIND_AUDIO
	# Không có kind riêng cho video → coi như tệp đính kèm (UI hiện card tải về).
	return KIND_FILE


def _validate_mime(upload, kind_hint):
	"""Xác định mime hợp lệ. Trả (mime, error_response|None)."""
	ext = os.path.splitext(getattr(upload, 'name', '') or '')[1].lower()
	declared = (getattr(upload, 'content_type', '') or '').split(';')[0].strip().lower()
	sniffed = _sniff_mime(upload)

	# Tệp nhị phân: mime thật từ magic bytes (không tin content_type client).
	if sniffed:
		return sniffed, None
	# Tệp văn bản: không có magic bytes → phải dựa vào đuôi nằm trong allow-list.
	if ext in ALLOWED_EXT:
		mime = ALLOWED_EXT[ext]
		if mime.startswith('image/') or mime.startswith('audio/') or mime == 'video/mp4':
			return mime, None
		# Văn bản/office: đuôi hợp lệ là đủ, mime lấy theo đuôi để không phụ thuộc client.
		return mime, None
	return None, error_response(message='FILE_TYPE_NOT_ALLOWED', status=400, errors={'mime': declared or ext, 'ext': ext})


def save_attachment(upload, conversation_id, kind_hint=''):
	"""Lưu 1 tệp đính kèm. Trả (dict, error).

	dict: {kind, file_url, file_name, file_size, mime, storage_path}
	"""
	if upload is None:
		return None, error_response(message='NO_FILE', status=400)
	ext = os.path.splitext(getattr(upload, 'name', '') or '')[1].lower()
	limit = MAX_IMAGE_SIZE if (ext in ALLOWED_IMAGE_EXT or kind_hint == KIND_IMAGE) else MAX_FILE_SIZE

	size = _get_size(upload)
	if size <= 0:
		return None, error_response(message='FILE_EMPTY', status=400)
	if size > limit:
		return None, error_response(message='FILE_TOO_LARGE', status=400, errors={'size': size, 'max_bytes': limit})

	mime, error = _validate_mime(upload, kind_hint)
	if error is not None:
		return None, error

	from services.storage_service import StorageService

	kind = _normalize_kind(mime, kind_hint)
	safe_name = _build_safe_name(getattr(upload, 'name', ''), mime)
	storage_path = _relative_path(conversation_id, kind, safe_name)
	saved = StorageService.save_uploaded_file(storage_path, upload)
	try:
		file_url = StorageService.get_file_url(saved)
	except Exception:  # noqa: BLE001 — storage backend có thể không hỗ trợ url()
		file_url = f'{settings.MEDIA_URL}{saved}'
	return (
		{
			'kind': kind,
			'file_url': str(file_url)[:500],
			'file_name': (getattr(upload, 'name', '') or safe_name)[:255],
			'file_size': size,
			'mime': mime[:128],
			'storage_path': saved,
		},
		None,
	)


def collect_uploads(request, params=None):
	"""Ghép file multipart với metadata FE gửi (cùng cách `systems_details` làm).

	Client không gửi metadata → suy ra luôn từ `request.FILES`.
	"""
	uploads = getattr(request, 'FILES', None) or {}
	metadata = [item for item in ((params or {}).get('files') or []) if isinstance(item, dict)]
	collected = []
	used_keys = set()
	for item in metadata:
		index = item.get('__file_index')
		upload = uploads.get(str(index)) if index is not None else None
		if index is not None:
			used_keys.add(str(index))
		# Client khai metadata nhưng không gửi file tương ứng → bỏ, không echo file "ma".
		if upload is None:
			continue
		collected.append({'file': upload, 'kind': item.get('kind') or ''})
	for key, upload in uploads.items():
		if key in used_keys:
			continue
		collected.append({'file': upload, 'kind': ''})
	return collected


def upload_attachments(user, conversation_id, uploads):
	"""Upload nhiều tệp cho 1 room. Trả (list[dict], error).

	- Chỉ MEMBER hiện tại được upload (room kín).
	- Phòng đã giải tán thì không nhận tệp nào.
	"""
	from .models import Conversation

	conversation = Conversation.objects.filter(id=conversation_id).first() if conversation_id else None
	if conversation is None:
		return None, error_response(message='NOT_FOUND', status=404)
	if get_membership(conversation.id, user.id) is None:
		return None, error_response(message='NOT_MEMBER', status=403)
	dissolved_error = require_active_room(conversation)
	if dissolved_error is not None:
		return None, dissolved_error
	if not uploads:
		return None, error_response(message='NO_FILE', status=400)
	if len(uploads) > MAX_FILES_PER_MESSAGE:
		return None, error_response(message='TOO_MANY_FILES', status=400, errors={'max': MAX_FILES_PER_MESSAGE})

	results = []
	for item in uploads:
		attachment, error = save_attachment(item.get('file'), conversation.id, item.get('kind') or '')
		if error is not None:
			return None, error
		results.append(attachment)
	return results, None