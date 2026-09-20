"""
API payload encryption middleware (mutual handshake — mức 2).

Enabled only when settings.ENABLE_API_ENCRYPTION is True.
Cơ chế khóa 2 CHIỀU KHÁC NHAU:
    REQUEST (client → server): AES key bọc bằng RSA **server public key**
        (certs/public_key.pem) → server unwrap bằng certs/private_key.pem.
        Stateless — không phụ thuộc session cache (chịu được restart).
    RESPONSE (server → client): AES key MỚI bọc bằng RSA **client public key**
        (lấy từ session của handshake) → client unwrap bằng private key của nó.

Client side:
    1. GET /api/crypto/public_key   → nhận server public key (PEM)
    2. Sinh keypair RSA-OAEP của mình (dùng để nhận response)
    3. POST /api/crypto/handshake với body {"client_public_key": PEM} đã mã hóa
       bằng server public key → nhận {session_id, encrypt_request}
    4. Các request sau: headers X-Session-Id + Content-Type: encrypted+json
       body: {"payload", "nonce", "key": <AES key bọc server pubkey>}
    5. Response mã hóa bằng client public key với cùng wire format.

Requests without an encrypted content-type are passed through untouched,
so /admin, /api/health, docs, and plaintext API calls keep working.
"""

import json

from django.conf import settings
from django.http import JsonResponse, QueryDict
from django.utils.deprecation import MiddlewareMixin

from libs.crypto.rsa_utils import (
    CryptoError,
    decrypt_payload,
    encrypt_payload,
    generate_aes_key,
    load_client_public_key,
    pack_hybrid_payload,
    unpack_hybrid_payload,
)
from libs.crypto.session_store import get_session_aes_key, get_session_client_public_key

ENCRYPTED_CONTENT_TYPE = "application/encrypted+json"


class EncryptionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._crypto_aes_key = None
        request._crypto_client_public_key = None

        if not getattr(settings, "ENABLE_API_ENCRYPTION", False):
            return None
        if self._is_excluded(request.path):
            return None

        content_type = (request.content_type or "").split(";")[0].strip().lower()
        if content_type != ENCRYPTED_CONTENT_TYPE:
            # Request plaintext (GET/DELETE hoặc body không mã hóa): vẫn mã hóa
            # RESPONSE nếu client gửi kèm X-Session-Id từ handshake.
            session_id = request.headers.get("X-Session-Id")
            if session_id:
                request._crypto_client_public_key = get_session_client_public_key(session_id, settings.CRYPTO_SESSION_TTL)

            # GET/HEAD mã hóa "qua query": browser (XHR) không cho gửi body trên GET
            # nên client đóng gói params vào query param `_e` (base64url của wire
            # format {payload, nonce, key}). Giải mã + đổ vào request.GET như bình thường.
            if request.method in ("GET", "HEAD") and request.GET.get("_e"):
                try:
                    import base64

                    wire = json.loads(base64.urlsafe_b64decode(request.GET["_e"] + "=" * (-len(request.GET["_e"]) % 4)))
                    if isinstance(wire, dict) and wire.get("key"):
                        plaintext = unpack_hybrid_payload(wire)
                    elif isinstance(wire, dict) and session_id:
                        aes_key = get_session_aes_key(session_id, settings.CRYPTO_SESSION_TTL)
                        if aes_key is None:
                            return self._reject(request, "Invalid or expired session")
                        plaintext = decrypt_payload(aes_key, wire.get("payload", ""), wire.get("nonce", ""))
                    else:
                        return self._reject(request, "Invalid encrypted query payload")
                    query = QueryDict(mutable=True)
                    for key, value in (json.loads(plaintext or b"{}") if plaintext else {}).items():
                        if isinstance(value, (list, tuple)):
                            query.setlist(key, [str(item) for item in value])
                        else:
                            query[key] = value if isinstance(value, str) else json.dumps(value)
                    request.GET = query
                    request.META["QUERY_STRING"] = query.urlencode()
                except (ValueError, CryptoError) as exc:
                    return self._reject(request, str(exc))
            return None
        session_id = request.headers.get("X-Session-Id")

        # Base64 inflates by ~4/3: reject oversized requests before decoding
        raw_len = len(request.body or b"")
        max_b64 = getattr(settings, "ENCRYPTION_MAX_BODY_SIZE", 15 * 1024 * 1024)
        if raw_len > max_b64 * 4 // 3 + 64:
            return self._reject(request, "Payload too large")

        try:
            body = json.loads(request.body or b"{}")
        except ValueError as exc:
            return self._reject(request, str(exc))

        # ---- Mode mới (khuyến nghị): AES key bọc bằng SERVER public key ----
        # Stateless; dùng được cho mọi request kể cả handshake (chưa có session).
        if isinstance(body, dict) and body.get("key"):
            try:
                plaintext = unpack_hybrid_payload(body)
            except CryptoError as exc:
                return self._reject(request, str(exc))
        else:
            # ---- Mode cũ (tương thích ngược): AES session key từ handshake ----
            if not session_id:
                return self._reject(request, "Missing X-Session-Id header")
            aes_key = get_session_aes_key(session_id, settings.CRYPTO_SESSION_TTL)
            if aes_key is None:
                return self._reject(request, "Invalid or expired session")
            try:
                plaintext = decrypt_payload(aes_key, body.get("payload", ""), body.get("nonce", ""))
            except (ValueError, CryptoError) as exc:
                return self._reject(request, str(exc))
            request._crypto_aes_key = aes_key

        # ---- Chiều RESPONSE: cần client public key để mã hóa kết quả trả về ----
        # Nguồn 1: session của handshake (client gửi kèm X-Session-Id) — dùng cho
        # mọi request sau handshake.
        if session_id:
            request._crypto_client_public_key = get_session_client_public_key(session_id, settings.CRYPTO_SESSION_TTL)
        # Nguồn 2: request tự mang client_public_key trong body (handshake — lúc này
        # session CHƯA tồn tại nên không tra được ở trên) → trích từ body đã giải mã.
        if request._crypto_client_public_key is None:
            request._crypto_client_public_key = self._extract_client_public_key(plaintext)

        # ---- Request GET/DELETE mã hóa: params nằm trong body đã giải mã ----
        # Đổ vào request.GET để view đọc request.query_params như bình thường
        # (URL không còn query string → params không lộ trong access log).
        if request.method in ("GET", "DELETE", "HEAD"):
            try:
                params = json.loads(plaintext or b"{}")
            except ValueError:
                params = None
            if isinstance(params, dict):
                query = QueryDict(mutable=True)
                for key, value in params.items():
                    if isinstance(value, (list, tuple)):
                        query.setlist(key, [str(item) for item in value])
                    elif value is None:
                        query[key] = ""
                    else:
                        query[key] = value if isinstance(value, str) else json.dumps(value)
                request.GET = query
                request.META["QUERY_STRING"] = query.urlencode()

        # Feed the decrypted body to DRF as a normal JSON request
        request._body = plaintext
        request._crypto_original_body = plaintext
        request.content_type = "application/json"
        request.META["CONTENT_TYPE"] = "application/json"
        request.META["HTTP_CONTENT_TYPE"] = "application/json"
        request.content_params = {}
        return None

    def process_response(self, request, response):
        if not getattr(settings, "ENABLE_API_ENCRYPTION", False):
            return response
        if self._is_excluded(request.path):
            return response
        if not response.status_code or response.status_code == 204:
            return response

        client_public_key_pem = getattr(request, "_crypto_client_public_key", None)
        aes_key = getattr(request, "_crypto_aes_key", None)
        # Request plaintext → response plaintext (client không có khóa để giải mã)
        if client_public_key_pem is None and aes_key is None:
            return response

        # DRF Response chưa render tại thời điểm middleware chạy →
        # response.content sẽ raise ContentNotRenderedError; dùng rendered_content.
        try:
            plaintext = response.rendered_content if hasattr(response, "rendered_content") else response.content
        except Exception:
            return response
        if not plaintext:
            return response

        try:
            if client_public_key_pem is not None:
                # Mode mới: AES key MỚI (random) bọc bằng CLIENT public key (mỗi response 1 key)
                packed = pack_hybrid_payload(generate_aes_key(), plaintext, load_client_public_key(client_public_key_pem))
            else:
                # Mode cũ: dùng lại AES session key (không kèm 'key' trong body)
                payload_b64, nonce_b64 = encrypt_payload(aes_key, plaintext)
                packed = {"payload": payload_b64, "nonce": nonce_b64}
        except CryptoError:
            return response
        response.content = json.dumps(packed).encode()
        # Đánh dấu đã render: nếu không, Django sẽ gọi response.render() sau middleware
        # và GHI ĐÈ nội dung mã hóa bằng plaintext JSON.
        if hasattr(response, "_is_rendered"):
            response._is_rendered = True
        response["Content-Type"] = ENCRYPTED_CONTENT_TYPE
        response["Content-Length"] = str(len(response.content))
        return response

    # ------------------------------------------------------------------

    def _is_excluded(self, path: str) -> bool:
        prefixes = getattr(settings, "ENCRYPTION_EXCLUDED_PREFIXES", [])
        return any(path == p or path.startswith(p.rstrip("/") + "/") for p in prefixes)

    def _extract_client_public_key(self, plaintext) -> str | None:
        """Trích client RSA public key PEM từ body request đã giải mã.

        Dùng cho handshake: request mang {"client_public_key": "<PEM>"} nhưng
        session chưa tồn tại nên chưa tra được từ session_store.
        """
        if not plaintext:
            return None
        try:
            decoded = json.loads(plaintext)
        except ValueError:
            return None
        if not isinstance(decoded, dict):
            return None
        candidate = decoded.get("client_public_key") or decoded.get("public_key")
        if isinstance(candidate, str) and "BEGIN PUBLIC KEY" in candidate:
            return candidate
        return None

    def _reject(self, request, message: str):
        # Plain JsonResponse (DRF Response is not renderable at this stage)
        response = JsonResponse(
            {
                "success": False,
                "data": None,
                "message": message,
                "errors": None,
                "meta": {"status_code": 400},
            },
            status=400,
        )
        request._crypto_aes_key = None  # Do not re-encrypt the error itself
        request._crypto_client_public_key = None
        return response
