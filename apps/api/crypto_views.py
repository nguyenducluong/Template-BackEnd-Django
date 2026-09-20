"""
Crypto endpoints:

    GET  /api/v1/crypto/public_key
        Trả RSA public key của SERVER (PEM) để client mã hóa REQUEST.
        Public, không auth — public key vốn công khai.

    POST /api/v1/crypto/handshake
        Body (đã mã hóa bằng SERVER public key, do EncryptionMiddleware giải mã):
            {"client_public_key": "<client RSA public key PEM>"}
        Server lưu client public key theo session_id → dùng để mã hóa RESPONSE.
        Resp (mã hóa ngược lại bằng client public key):
            {"session_id", "expires_in", "encrypt_request"}

Client quyết định bật/tắt mã hóa cho mọi API sau DỰA VÀO handshake này:
    success = true  → bật mã hóa (request + response)
    400 / lỗi       → giữ plaintext (ENABLE_API_ENCRYPTION đang tắt)
"""

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from django.conf import settings
from django.utils.translation import gettext as _

from libs.crypto.rsa_utils import CryptoError, load_client_public_key, get_server_public_key
from libs.crypto.session_store import create_session
from libs.responses import error_response, success_response


class ServerPublicKeyView(APIView):
    """GET /api/v1/crypto/public_key — RSA public key của server (PEM)."""

    authentication_classes = []  # Client cần key này trước khi có bất kỳ token nào
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "crypto_handshake"
    http_method_names = ["get", "options"]

    @extend_schema(
        tags=["Crypto"],
        responses={200: dict},
    )
    def get(self, request):
        enabled = getattr(settings, "ENABLE_API_ENCRYPTION", False)
        data = {"enabled": enabled, "algorithm": "RSA-OAEP-SHA256"}
        if enabled:
            # Chỉ đọc key khi mã hóa đang bật (file có thể chưa tồn tại ở dev)
            try:
                pem = get_server_public_key().public_bytes(
                    encoding=Encoding.PEM,
                    format=PublicFormat.SubjectPublicKeyInfo,
                ).decode()
            except Exception:
                return error_response(
                    message=_("Server RSA public key is unavailable."),
                    status=500,
                )
            data["public_key"] = pem
        return success_response(data=data)


class CryptoHandshakeView(APIView):
    """
    POST /api/v1/crypto/handshake
    Body (đã giải mã bởi middleware): {"client_public_key": "<PEM>"}
    Resp: {"session_id", "expires_in", "encrypt_request"}
    """

    authentication_classes = []  # Handshake must work pre-auth
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "crypto_handshake"  # limit abuse (session + RSA CPU cost)
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["Crypto"],
        request={"application/json": {"type": "object", "properties": {
            "client_public_key": {"type": "string", "description": "Client RSA public key (PEM)"},
        }}},
        responses={200: dict, 400: dict},
    )
    def post(self, request):
        # Server TẮT mã hóa (DJANGO_ENV=development) → không tạo session ảo.
        # Nếu không chặn ở đây, client sẽ tưởng server bật mã hóa rồi gửi
        # payload encrypted+json mà middleware bỏ qua → DRF 415 Unsupported media type.
        if not getattr(settings, "ENABLE_API_ENCRYPTION", False):
            return error_response(
                message=_("API encryption is disabled on this server."),
                status=400,
            )

        body = request.data or {}
        # Hỗ trợ cả tên cũ 'public_key' để không phá client/test cũ
        client_public_key_pem = body.get("client_public_key") or body.get("public_key")
        if not client_public_key_pem or "BEGIN PUBLIC KEY" not in str(client_public_key_pem):
            return error_response(
                message=_("Missing or invalid 'client_public_key' (RSA PEM required)"),
                status=400,
            )

        try:
            load_client_public_key(str(client_public_key_pem))
        except CryptoError:
            return error_response(message=_("Invalid client public key"), status=400)

        session = create_session(
            client_public_key_pem=str(client_public_key_pem),
            ttl=settings.CRYPTO_SESSION_TTL,
        )
        # encrypt_request: client dựa vào đây + session_id để bật mã hóa các API sau
        session["encrypt_request"] = True

        # Khai báo cho EncryptionMiddleware: response này phải mã hóa bằng CLIENT
        # public key. LƯU Ý: `request` ở đây là DRF Request wrapper — phải gán lên
        # Django HttpRequest gốc (request._request), nếu không
        # middleware.process_response sẽ không đọc thấy và trả plaintext.
        request._request._crypto_client_public_key = str(client_public_key_pem)
        return success_response(data=session, message=_("Handshake successful"))
