"""Resource `attachments` — upload tệp cho tin nhắn.

POST /api/v1/messages/dispatch  {resource: 'attachments', action: 'upload',
                                 id: <conversation_id>, params: {files: [...]}}

FE gui multipart (co Blob ⇒ `axios_post` tu build FormData): file o key "0","1",…
va metadata {__file_index, kind} trong `params.files` — xem `services/upload.py`.

CHOI LUONG:
  1. Upload tệp  →  server luu va tra metadata {file_url, file_name, file_size, mime, kind}
  2. Client gui tin nhan `kind=image|file|audio` kem `file_url` do (1) tra ve
Nen socket CHI nhan metadata, khong bao gio nhan binary.
"""

from libs.responses import created_response, error_response

from .services import upload as upload_svc
from .utils import parse_uuid


def handle_upload(action, user, item_id, data, params, request):
	"""Upload 1 hoac nhieu tep vao 1 room. Chi thanh vien hien tai duoc phep."""
	if action != 'upload':
		return error_response(message='Unknown action.', status=400)
	if request is None:
		return error_response(message='REQUEST_REQUIRED', status=400)

	# `id` đến từ client nên phải qua `parse_uuid`: chuỗi rác làm Django ném
	# `ValidationError` khi lọc UUIDField ⇒ 500 thay vì 400 rõ ràng.
	conversation_id = parse_uuid(item_id or data.get('conversation_id'))
	if conversation_id is None:
		return error_response(message='ID_INVALID', status=400)

	uploads = upload_svc.collect_uploads(request, params)
	attachments, error = upload_svc.upload_attachments(user, conversation_id, uploads)
	if error is not None:
		return error

	# `storage_path` chi de doi file sau nay — khong tra ra client.
	payload = [{key: value for key, value in item.items() if key != 'storage_path'} for item in attachments]
	return created_response(data={'conversation_id': str(conversation_id), 'attachments': payload})