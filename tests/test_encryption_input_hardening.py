"""Test middleware encryption: input rác phải trả 400 SẠCH, không phải 500.

Bug gốc: nhánh GET với query `_e` chỉ bắt `(ValueError, CryptoError)`. Vì `wire`
là JSON do CLIENT gửi lên, các shape lệch kiểu (`{"key": 123}`,
`{"payload": {"x": 1}}`) ném `TypeError`/`AttributeError` lọt khỏi except ⇒
HTTP 500 + traceback lộ chi tiết thay vì 400 gọn.
"""

import base64
import json

from django.test import RequestFactory, SimpleTestCase, override_settings


def _b64(obj):
	raw = json.dumps(obj).encode()
	return base64.urlsafe_b64encode(raw).decode().rstrip("=")


class EncryptedQueryMalformedTests(SimpleTestCase):
	def setUp(self):
		self.factory = RequestFactory()

	def _get(self, wire):
		request = self.factory.get("/api/v1/systems/details", {"_e": _b64(wire)})
		from libs.middlewares.encryption import EncryptionMiddleware

		return EncryptionMiddleware(lambda r: None).process_request(request)

	@override_settings(ENABLE_API_ENCRYPTION=True)
	def test_payload_of_wrong_type_is_rejected_not_500(self):
		"""`payload` là dict thay vì chuỗi ⇒ TypeError nếu không bắt."""
		response = self._get({"payload": {"x": 1}, "nonce": "abc", "key": {"k": "v"}})
		self.assertIsNotNone(response, "phải trả response lỗi")
		self.assertEqual(response.status_code, 400)

	@override_settings(ENABLE_API_ENCRYPTION=True)
	def test_key_of_wrong_type_is_rejected(self):
		response = self._get({"key": 12345})
		self.assertIsNotNone(response)
		self.assertEqual(response.status_code, 400)

	@override_settings(ENABLE_API_ENCRYPTION=True)
	def test_garbage_key_field_does_not_raise(self):
		"""Chuỗi rác trong `key` ⇒ CryptoError, vẫn phải là 400 gọn."""
		response = self._get({"key": "khong-phai-khoa-hop-le", "payload": "", "nonce": ""})
		self.assertIsNotNone(response)
		self.assertEqual(response.status_code, 400)

	@override_settings(ENABLE_API_ENCRYPTION=True)
	def test_wire_not_a_dict_is_rejected(self):
		response = self._get([1, 2, 3])
		self.assertIsNotNone(response)
		self.assertEqual(response.status_code, 400)