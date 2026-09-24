"""
E2E auth (login / me / refresh) — kiểm tra 3 API trả kèm dữ liệu Organization +
Shift đã join, đi qua KÊNH MÃ HÓA 2 CHIỀU (request mã hóa bằng server public
key; response mã hóa bằng client public key).

Chạy:  python manage.py test tests.test_join_e2e -v 2
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

from apps.accounts.models import User
from apps.info.models import Organization, Shift

API = "/api/v1"  # APPEND_SLASH=False → path KHÔNG có '/' cuối
ENCRYPTED_CONTENT_TYPE = "application/encrypted+json"
PASSWORD = "SecurePass123"

_OAEP = asym_padding.OAEP(
    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


class EncryptedClient:
    """Client test mã hóa 2 chiều — mô phỏng STD/src/utils/crypto_session.jsx."""

    def __init__(self, django_client):
        self.http = django_client
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._server_pub = None
        self.session_id = None

    # ---- khóa ----
    def _client_public_pem(self) -> str:
        return self._private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def _pack(self, payload: bytes) -> str:
        """AES-256-GCM + bọc AES key bằng SERVER public key (chiều REQUEST)."""
        aes_key = AESGCM.generate_key(256)
        nonce = os.urandom(12)
        return json.dumps({
            "payload": base64.b64encode(AESGCM(aes_key).encrypt(nonce, payload, None)).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "key": base64.b64encode(self._server_pub.encrypt(aes_key, _OAEP)).decode(),
        })

    def _unpack(self, response) -> dict:
        """Giải mã response bằng RSA private key của client (chiều RESPONSE)."""
        body = json.loads(response.content)
        aes_key = self._private_key.decrypt(base64.b64decode(body["key"]), _OAEP)
        raw = AESGCM(aes_key).decrypt(
            base64.b64decode(body["nonce"]), base64.b64decode(body["payload"]), None
        )
        return json.loads(raw)

    def _envelope(self, response) -> dict:
        if response["Content-Type"].startswith(ENCRYPTED_CONTENT_TYPE):
            return self._unpack(response)
        return response.json()

    # ---- API ----
    def handshake(self) -> str:
        public_key = self.http.get(f"{API}/crypto/public_key")
        pem = public_key.json()["data"]["public_key"]
        self._server_pub = serialization.load_pem_public_key(pem.encode())

        response = self.http.post(
            f"{API}/crypto/handshake",
            data=self._pack(json.dumps({"client_public_key": self._client_public_pem()}).encode()),
            content_type=ENCRYPTED_CONTENT_TYPE,
        )
        assert response.status_code == 200, response.content
        self.session_id = self._unpack(response)["data"]["session_id"]
        return self.session_id

    def get(self, path: str, params=None, **extra):
        response = self.http.generic(
            "GET",
            f"{API}{path}",
            data=self._pack(json.dumps(params or {}).encode()),
            content_type=ENCRYPTED_CONTENT_TYPE,
            HTTP_X_SESSION_ID=self.session_id,
            **extra,
        )
        return response, self._envelope(response)

    def post(self, path: str, payload: dict, **extra):
        response = self.http.post(
            f"{API}{path}",
            data=self._pack(json.dumps(payload).encode()),
            content_type=ENCRYPTED_CONTENT_TYPE,
            HTTP_X_SESSION_ID=self.session_id,
            **extra,
        )
        return response, self._envelope(response)


# ---------------------------------------------------------------------------
# E2E: user trong DB test → 3 API auth phải trả đủ org + shift đã join
# ---------------------------------------------------------------------------

@override_settings(ENABLE_API_ENCRYPTION=True)
class JoinedOrgShiftE2ETests(TestCase):
    """login / me / refresh — dữ liệu Organization + Shift join, qua kênh mã hóa."""

    databases = "__all__"

    def setUp(self):
        cache.clear()
        # Cây tổ chức 4 cấp: Location(3) → Part(2) → Group(1) → Team(0)
        self.org_location = Organization.objects.create(name="IQC 2P", level=3, sort=1, is_use=True)
        self.org_part = Organization.objects.create(name="IQC G", level=2, sort=2, parent=self.org_location, is_use=True)
        self.org_group = Organization.objects.create(name="SET QC Team", level=1, sort=3, parent=self.org_part, is_use=True)
        self.org_team = Organization.objects.create(name="Incoming MEC", level=0, sort=4, parent=self.org_group, is_use=True)
        self.shift = Shift.objects.create(shift_vi="Ca 2A1", shift_en="Shift 2A1", shift_kr="교대 2A1")

        self.user = User.objects.create(
            gen_id="12345678",
            knox_id="e2euser",
            full_name="E2E Tester",
            org=self.org_team,
            shift=self.shift,
            status=User.StatusChoices.APPROVED,
        )
        self.user.set_password(PASSWORD)
        self.user.save()

        self.crypto = EncryptedClient(Client())
        self.crypto.handshake()

    # -- login ---------------------------------------------------------------
    def test_login_returns_joined_org_and_shift(self):
        response, envelope = self.crypto.post(
            "/accounts/auth/login",
            {"account": self.user.gen_id, "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response["Content-Type"].startswith(ENCRYPTED_CONTENT_TYPE))
        self.assertTrue(envelope["success"])
        data = envelope["data"]

        user = data["user"]
        self.assertEqual(user["org_id"], self.org_team.id)
        self.assertEqual(user["org_full_path"], self.org_team.cached_full_path)
        self.assertEqual(user["org_full_name"], self.org_team.cached_full_name)
        self.assertEqual(user["shift_en"], self.shift.shift_en)

        # user_info (port Laravel) phải có org_full_name + ipv4 + status_label
        self.assertEqual(data["user_info"]["org_full_name"], self.org_team.cached_full_name)
        self.assertIn("ipv4", data["user_info"])
        self.assertIn("status_label", data["user_info"])
        self.assertIn(data["auth_page"], ("user_info", "change_password"))

    def test_login_via_knox_id_also_joined(self):
        """Đăng nhập bằng KnoxID → cùng shape dữ liệu join."""
        response, envelope = self.crypto.post(
            "/accounts/auth/login",
            {"account": self.user.knox_id, "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(envelope["data"]["user"]["org_id"], self.org_team.id)

    # -- me ------------------------------------------------------------------
    def test_me_returns_joined_org_and_shift(self):
        _response, login = self.crypto.post(
            "/accounts/auth/login",
            {"account": self.user.gen_id, "password": PASSWORD},
        )
        response, envelope = self.crypto.get(
            "/accounts/auth/me",
            HTTP_AUTHORIZATION="Bearer " + login["data"]["access"],
        )
        self.assertEqual(response.status_code, 200, response.content)
        # Request có session → response mã hóa; Authorization đọc từ header
        self.assertTrue(response["Content-Type"].startswith(ENCRYPTED_CONTENT_TYPE))
        self.assertTrue(envelope["success"])
        self.assertEqual(envelope["data"]["org_full_path"], self.org_team.cached_full_path)
        self.assertEqual(envelope["data"]["shift_vi"], self.shift.shift_vi)

    # -- refresh -------------------------------------------------------------
    def test_refresh_returns_joined_org_and_shift(self):
        _response, login = self.crypto.post(
            "/accounts/auth/login",
            {"account": self.user.gen_id, "password": PASSWORD},
        )
        response, envelope = self.crypto.post(
            "/accounts/auth/refresh",
            {"refresh": login["data"]["refresh"]},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(envelope["success"])
        self.assertEqual(envelope["data"]["user"]["org_id"], self.org_team.id)
        self.assertEqual(envelope["data"]["user"]["org_full_name"], self.org_team.cached_full_name)
        self.assertEqual(envelope["data"]["user"]["shift_kr"], self.shift.shift_kr)
        # Rotation: refresh token mới phải khác token cũ
        self.assertNotEqual(envelope["data"]["refresh"], login["data"]["refresh"])

    # -- an toàn: sai mật khẩu ----------------------------------------------
    def test_wrong_password_error_is_encrypted(self):
        response, envelope = self.crypto.post(
            "/accounts/auth/login",
            {"account": self.user.gen_id, "password": "WrongPassword@1"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response["Content-Type"].startswith(ENCRYPTED_CONTENT_TYPE))
        self.assertIs(envelope["success"], False)
        self.assertTrue(envelope["message"])
