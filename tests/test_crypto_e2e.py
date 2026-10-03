"""
E2E tests cho mã hóa payload API 2 CHIỀU (mutual handshake).

Chạy:  python manage.py test tests.test_crypto_e2e -v 2

Cơ chế khóa 2 chiều khác nhau:
    REQUEST  : AES key bọc bằng RSA **server public key** (stateless, không cần session)
    RESPONSE : AES key MỚI bọc bằng RSA **client public key** (client tự sinh, gửi
               trong handshake; server lưu theo session_id)

Kịch bản test:
    1. GET  crypto/public_key        → server public key + cờ enabled
    2. POST crypto/handshake (mã hóa)→ session_id + encrypt_request (response mã hóa)
    3. GET  API có params mã hóa     → request + response đều mã hóa
    4. POST login sai mật khẩu       → response LỖI cũng được mã hóa
    5. Request plaintext             → response plaintext (tương thích ngược)
    6. Payload bị sửa (tamper)       → 400
    7. Body mã hóa không có session  → vẫn giải mã được (stateless), response plaintext
    8. Mode CŨ (AES session key)     → vẫn được chấp nhận (không phá client cũ)
"""

import base64
import json
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from libs.crypto.rsa_utils import get_server_public_key

ENCRYPTED_CONTENT_TYPE = "application/encrypted+json"
API = "/api/v1"  # APPEND_SLASH=False → mọi path KHÔNG có '/' cuối

_OAEP = asym_padding.OAEP(
    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


# ---------------------------------------------------------------------------
# Helper mã hóa / giải mã phía "client" (mô phỏng STD/src/utils/crypto_session.jsx)
# ---------------------------------------------------------------------------

def pack_for(public_pem: str, plaintext: bytes) -> dict:
    """AES-256-GCM + bọc AES key bằng RSA public key → wire format REQUEST."""
    aes_key = AESGCM.generate_key(256)
    nonce = os.urandom(12)
    ct = AESGCM(aes_key).encrypt(nonce, plaintext, None)
    pub = serialization.load_pem_public_key(public_pem.encode())
    return {
        "payload": base64.b64encode(ct).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "key": base64.b64encode(pub.encrypt(aes_key, _OAEP)).decode(),
    }


def pack_with_session_key(session_key: bytes, plaintext: bytes) -> dict:
    """Wire format MODE CŨ: {"payload","nonce"} mã hóa bằng session AES key."""
    nonce = os.urandom(12)
    ct = AESGCM(session_key).encrypt(nonce, plaintext, None)
    return {
        "payload": base64.b64encode(ct).decode(),
        "nonce": base64.b64encode(nonce).decode(),
    }


def unwrap_key(private_key, packed: dict) -> bytes:
    """Unwrap AES key của response bằng RSA private key của client."""
    return private_key.decrypt(base64.b64decode(packed["key"]), _OAEP)


def decrypt_with(private_key, packed: dict) -> dict:
    """Giải mã response hybrid → envelope { success, data, message, errors, meta }."""
    aes_key = unwrap_key(private_key, packed)
    raw = AESGCM(aes_key).decrypt(
        base64.b64decode(packed["nonce"]), base64.b64decode(packed["payload"]), None
    )
    return json.loads(raw)


def decrypt_with_session_key(session_key: bytes, packed: dict) -> dict:
    """Giải mã response mode CŨ (không kèm 'key')."""
    raw = AESGCM(session_key).decrypt(
        base64.b64decode(packed["nonce"]), base64.b64decode(packed["payload"]), None
    )
    return json.loads(raw)


def _server_public_pem() -> str:
    """RSA public key của server (PEM) — dùng để mã hóa REQUEST."""
    return get_server_public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def _public_pem(private_key) -> str:
    """Xuất public key (PEM) từ RSA private key — mô phỏng WebCrypto exportKey('spki')."""
    return private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


class CryptoRequestEncryptionTests(TestCase):
    """Kịch bản 1–8: request mã hóa + response mã hóa + tương thích ngược."""

    def setUp(self):
        cache.clear()  # xóa session + counter throttle giữa các test
        self.client = Client()
        self.server_pub_pem = _server_public_pem()
        self.client_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.client_pub_pem = _public_pem(self.client_priv)

    # -- (1) server public key: endpoint plaintext ---------------------------
    @override_settings(ENABLE_API_ENCRYPTION=True)
    def test_public_key_endpoint_returns_server_key(self):
        response = self.client.get(f"{API}/crypto/public_key")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response["Content-Type"].startswith(ENCRYPTED_CONTENT_TYPE))
        envelope = response.json()
        self.assertTrue(envelope["success"])
        self.assertIs(envelope["data"]["enabled"], True)
        self.assertIn("BEGIN PUBLIC KEY", envelope["data"]["public_key"])

    @override_settings(ENABLE_API_ENCRYPTION=False)
    def test_public_key_reports_disabled_when_flag_off(self):
        """Server tắt mã hóa → client biết để dùng plaintext cả phiên."""
        response = self.client.get(f"{API}/crypto/public_key")
        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["data"]["enabled"], False)

    # -- (2) handshake: 2 chiều đều mã hóa ----------------------------------
    @override_settings(ENABLE_API_ENCRYPTION=True)
    def test_handshake_encrypted_both_ways(self):
        self.assertTrue(self._handshake())

    @override_settings(ENABLE_API_ENCRYPTION=False)
    def test_handshake_rejected_when_encryption_off(self):
        body = pack_for(self.server_pub_pem, json.dumps({"client_public_key": self.client_pub_pem}).encode())
        response = self.client.post(
            f"{API}/crypto/handshake",
            data=json.dumps(body),
            content_type=ENCRYPTED_CONTENT_TYPE,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIs(response.json()["success"], False)

    @override_settings(ENABLE_API_ENCRYPTION=True)
    def test_handshake_requires_client_public_key(self):
        """Thiếu client public key → 400 (server không có khóa mã hóa response)."""
        body = pack_for(self.server_pub_pem, b"{}")
        response = self.client.post(
            f"{API}/crypto/handshake",
            data=json.dumps(body),
            content_type=ENCRYPTED_CONTENT_TYPE,
        )
        self.assertEqual(response.status_code, 400)

    # -- (3) GET có params: request + response đều mã hóa --------------------
    @override_settings(ENABLE_API_ENCRYPTION=True)
    def test_get_params_encrypted_both_ways(self):
        session_id = self._handshake()
        body = pack_for(self.server_pub_pem, json.dumps({"lang": "vi"}).encode())
        response = self.client.generic(
            "GET",
            f"{API}/systems/default/options_authentication",
            data=json.dumps(body),
            content_type=ENCRYPTED_CONTENT_TYPE,
            HTTP_X_SESSION_ID=session_id,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith(ENCRYPTED_CONTENT_TYPE))
        envelope = decrypt_with(self.client_priv, json.loads(response.content))
        self.assertTrue(envelope["success"])
        self.assertTrue(envelope["data"]["init"]["title"]["sign_in"])

    # -- (4) nhánh LỖI cũng đi qua kênh mã hóa ------------------------------
    @override_settings(ENABLE_API_ENCRYPTION=True)
    def test_error_response_is_encrypted_too(self):
        """Request sai (thiếu field bắt buộc) → 400 nhưng vẫn mã hóa response."""
        session_id = self._handshake()
        body = pack_for(self.server_pub_pem, json.dumps({"account": ""}).encode())
        response = self.client.post(
            f"{API}/accounts/auth/login",
            data=json.dumps(body),
            content_type=ENCRYPTED_CONTENT_TYPE,
            HTTP_X_SESSION_ID=session_id,
        )
        self.assertGreaterEqual(response.status_code, 400)
        self.assertTrue(response["Content-Type"].startswith(ENCRYPTED_CONTENT_TYPE))
        envelope = decrypt_with(self.client_priv, json.loads(response.content))
        self.assertIs(envelope["success"], False)

    # -- (5) tương thích ngược: request plaintext → response plaintext -------
    @override_settings(ENABLE_API_ENCRYPTION=True)
    def test_plaintext_request_stays_plaintext(self):
        response = self.client.get(f"{API}/systems/default/options_authentication")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response["Content-Type"].startswith(ENCRYPTED_CONTENT_TYPE))
        self.assertTrue(response.json()["success"])

    # -- (6) chống sửa payload (tamper) -------------------------------------
    @override_settings(ENABLE_API_ENCRYPTION=True)
    def test_tampered_payload_rejected(self):
        good = pack_for(self.server_pub_pem, b'{"account": "x"}')
        bad = {**good, "payload": base64.b64encode(b"hacked").decode()}
        response = self.client.post(
            f"{API}/accounts/auth/login",
            data=json.dumps(bad),
            content_type=ENCRYPTED_CONTENT_TYPE,
        )
        self.assertEqual(response.status_code, 400)

    @override_settings(ENABLE_API_ENCRYPTION=True)
    def test_broken_wrapped_key_rejected(self):
        """AES key không unwrap được bằng server private key → 400."""
        body = pack_for(self.server_pub_pem, b"{}")
        body["key"] = base64.b64encode(os.urandom(256)).decode()
        response = self.client.post(
            f"{API}/accounts/auth/login",
            data=json.dumps(body),
            content_type=ENCRYPTED_CONTENT_TYPE,
        )
        self.assertEqual(response.status_code, 400)

    # -- (7) request mã hóa KHÔNG session (stateless) -----------------------
    @override_settings(ENABLE_API_ENCRYPTION=True)
    def test_encrypted_request_without_session(self):
        """Server vẫn giải mã (stateless) nhưng không biết client key → response plaintext."""
        body = pack_for(self.server_pub_pem, json.dumps({"lang": "vi"}).encode())
        response = self.client.generic(
            "GET",
            f"{API}/systems/default/options_authentication",
            data=json.dumps(body),
            content_type=ENCRYPTED_CONTENT_TYPE,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response["Content-Type"].startswith(ENCRYPTED_CONTENT_TYPE))

    # -- (8) mode CŨ (AES session key) vẫn hoạt động ------------------------
    @override_settings(ENABLE_API_ENCRYPTION=True)
    def test_legacy_session_key_mode_still_supported(self):
        session_id, session_key = self._handshake_and_get_session_key()
        body = pack_with_session_key(session_key, json.dumps({"lang": "vi"}).encode())
        response = self.client.generic(
            "GET",
            f"{API}/systems/default/options_authentication",
            data=json.dumps(body),
            content_type=ENCRYPTED_CONTENT_TYPE,
            HTTP_X_SESSION_ID=session_id,
        )
        self.assertEqual(response.status_code, 200)
        packed = json.loads(response.content)
        # Sau handshake server biết client public key → response dùng mode MỚI (kèm 'key')
        envelope = decrypt_with(self.client_priv, packed) if "key" in packed else decrypt_with_session_key(session_key, packed)
        self.assertTrue(envelope["success"])

    # ------------------------------------------------------------------
    def _handshake(self) -> str:
        """Handshake (request mã hóa) → session_id; response cũng mã hóa."""
        body = pack_for(
            self.server_pub_pem,
            json.dumps({"client_public_key": self.client_pub_pem}).encode(),
        )
        response = self.client.post(
            f"{API}/crypto/handshake",
            data=json.dumps(body),
            content_type=ENCRYPTED_CONTENT_TYPE,
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response["Content-Type"].startswith(ENCRYPTED_CONTENT_TYPE))
        envelope = decrypt_with(self.client_priv, json.loads(response.content))
        self.assertTrue(envelope["success"], envelope)
        self.assertIs(envelope["data"]["encrypt_request"], True)
        return envelope["data"]["session_id"]

    def _handshake_and_get_session_key(self):
        """Handshake → (session_id, AES session key) để test mode CŨ.

        `data.key` trong envelope handshake = AES session key bọc bằng CLIENT public key.
        """
        body = pack_for(
            self.server_pub_pem,
            json.dumps({"client_public_key": self.client_pub_pem}).encode(),
        )
        response = self.client.post(
            f"{API}/crypto/handshake",
            data=json.dumps(body),
            content_type=ENCRYPTED_CONTENT_TYPE,
        )
        self.assertEqual(response.status_code, 200, response.content)
        envelope = decrypt_with(self.client_priv, json.loads(response.content))
        self.assertTrue(envelope["success"], envelope)
        return envelope["data"]["session_id"], unwrap_key(self.client_priv, envelope["data"])

