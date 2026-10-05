"""API cua app messages - 1 dispatcher duy nhat: POST /api/v1/messages/dispatch."""

import json

from django.utils.translation import gettext as _

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.views import APIView

from libs.auth.throttling import ScopedRateThrottle
from libs.responses import error_response

from . import dispatch
from .serializers import DispatchSerializer


def _unwrap(value):
	"""Bỏ vỏ list/QueryDict của multipart, lấy giá trị thực sự bên trong.

	BUG ĐÃ GẬP: khi client (hoặc proxy) gửi trùng một field multipart, DRF trả
	về LIST (`['attachments']`) thay vì chuỗi ⇒ `DispatchSerializer` báo
	`'resource': ['Not a valid string.']` và `data` bị coi là list. Ở đây ta gỡ
	vỏ lấy phần tử cuối (giống cách QueryDict lấy giá trị cuối) cho khớp.
	"""
	# QueryDict: lấy giá trị cuối theo đúng ngữ nghĩa multipart.
	if hasattr(value, 'getlist'):
		values = value.getlist()
		return values[-1] if values else None
	if isinstance(value, (list, tuple)):
		return value[-1] if value else None
	return value


def _coerce_json(value):
	"""Chuẩn hoá field JSON của request multipart về dict.

	Multipart làm mọi field thành chuỗi, nên `data`/`params` về dạng JSON text.
	Ta cũng bỏ vỏ list (xem `_unwrap`) và chấp nhận dict sẵn có (request JSON).
	"""
	value = _unwrap(value)
	if value is None or value == '':
		return {}
	if isinstance(value, dict):
		return value
	if not isinstance(value, str):
		return {}
	try:
		parsed = json.loads(value)
	except (TypeError, ValueError):
		return {}
	return parsed if isinstance(parsed, dict) else {}


class MessagesDispatchView(APIView):
	"""POST /api/v1/messages/dispatch - dieu phoi theo {resource, action}."""

	permission_classes = [permissions.IsAuthenticated]
	throttle_classes = [ScopedRateThrottle]
	throttle_scope = 'messages'
	http_method_names = ['post', 'options']

	@extend_schema(tags=['Messages'], request=DispatchSerializer, responses={200: dict, 201: dict, 400: dict, 401: dict, 403: dict, 404: dict})
	def post(self, request):
		payload = request.data or {}
		if not hasattr(payload, 'get'):
			return error_response(message=_('Payload must be a JSON object.'), status=status.HTTP_400_BAD_REQUEST)
		# Bỏ vỏ list/QueryDict cho MỌI field trước khi validate: multipart đôi khi
		# bị proxy/client bọc thành list ⇒ serializer báo "Not a valid string".
		payload = {key: _unwrap(value) for key, value in dict(payload).items()}
		payload['data'] = _coerce_json(payload.get('data'))
		payload['params'] = _coerce_json(payload.get('params'))
		serializer = DispatchSerializer(data=payload)
		if not serializer.is_valid():
			return error_response(message=_('Invalid dispatch payload.'), errors=serializer.errors, status=status.HTTP_400_BAD_REQUEST)
		validated = serializer.validated_data
		if validated['resource'] not in dispatch.RESOURCES:
			return error_response(message=_('Unknown resource.'), status=status.HTTP_400_BAD_REQUEST)
		return dispatch.handle(
			resource=validated['resource'],
			action=validated['action'],
			user=request.user,
			item_id=validated.get('id'),
			data=validated.get('data') or {},
			params=validated.get('params') or {},
			language=getattr(request, 'LANGUAGE_CODE', None) or 'vi',
			request=request,
		)
