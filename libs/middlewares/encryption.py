"""
API payload encryption middleware (mutual handshake — mức 1, session-only).

Enabled only when settings.ENABLE_API_ENCRYPTION is True
(DJANGO_ENV != "development").

Client side:
    1. POST /api/crypto/handshake with its RSA public key PEM
       -> receives {"session_id", "key"(RSA-wrapped AES), "payload", "nonce"}
    2. Sends requests with headers:
           X-Session-Id: <session_id>
           Content-Type: application/encrypted+json
       body: {"payload": "<b64 AES-GCM ct>", "nonce": "<b64>"}
    3. Responses come back as application/encrypted+json with the same
       {"payload", "nonce"} format when a session is presented.

Requests without an encrypted content-type are passed through untouched,
so /admin, /api/health, docs, and plaintext API calls keep working.
"""

import json

from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from libs.crypto.rsa_utils import CryptoError, decrypt_payload, encrypt_payload
from libs.crypto.session_store import get_session_aes_key

ENCRYPTED_CONTENT_TYPE = "application/encrypted+json"


class EncryptionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request._crypto_aes_key = None

        if not getattr(settings, "ENABLE_API_ENCRYPTION", False):
            return None
        if self._is_excluded(request.path):
            return None

        session_id = request.headers.get("X-Session-Id")
        content_type = (request.content_type or "").split(";")[0].strip().lower()
        if content_type != ENCRYPTED_CONTENT_TYPE:
            return None  # Plaintext request — pass through
        if not session_id:
            return self._reject(request, "Missing X-Session-Id header")

        aes_key = get_session_aes_key(session_id, settings.CRYPTO_SESSION_TTL)
        if aes_key is None:
            return self._reject(request, "Invalid or expired session")

        # Base64 inflates by ~4/3: reject oversized requests before decoding
        raw_len = len(request.body or b"")
        max_b64 = getattr(settings, "ENCRYPTION_MAX_BODY_SIZE", 15 * 1024 * 1024)
        if raw_len > max_b64 * 4 // 3 + 64:
            return self._reject(request, "Payload too large")

        try:
            body = json.loads(request.body or b"{}")
            plaintext = decrypt_payload(
                aes_key, body.get("payload", ""), body.get("nonce", "")
            )
        except (ValueError, CryptoError) as exc:
            return self._reject(request, str(exc))

        # Feed the decrypted body to DRF as a normal JSON request
        request._crypto_aes_key = aes_key
        request._body = plaintext
        request._crypto_original_body = plaintext
        request.content_type = "application/json"
        request.META["CONTENT_TYPE"] = "application/json"
        request.META["HTTP_CONTENT_TYPE"] = "application/json"
        request.content_params = {}
        return None

    def process_response(self, request, response):
        aes_key = getattr(request, "_crypto_aes_key", None)
        if aes_key is None or not getattr(settings, "ENABLE_API_ENCRYPTION", False):
            return response
        if self._is_excluded(request.path):
            return response
        if not response.status_code or response.status_code == 204 or not response.content:
            return response

        plaintext = response.content
        # For DRF responses, encrypt the structured data (headers may be
        # re-rendered); for plain responses encrypt raw bytes.
        try:
            payload_b64, nonce_b64 = encrypt_payload(aes_key, plaintext)
        except CryptoError:
            return response
        response.content = json.dumps(
            {"payload": payload_b64, "nonce": nonce_b64}
        ).encode()
        response["Content-Type"] = ENCRYPTED_CONTENT_TYPE
        response["Content-Length"] = str(len(response.content))
        return response

    # ------------------------------------------------------------------

    def _is_excluded(self, path: str) -> bool:
        prefixes = getattr(settings, "ENCRYPTION_EXCLUDED_PREFIXES", [])
        return any(path == p or path.startswith(p.rstrip("/") + "/") for p in prefixes)

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
        return response
