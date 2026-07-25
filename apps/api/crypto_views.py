"""
Crypto handshake endpoint (mutual handshake, session-only).

Client POSTs its RSA public key PEM; the server creates an AES-256 session
key, stores it in Redis and returns it RSA-OAEP-wrapped with the CLIENT's
public key. Both sides then use the session key for AES-256-GCM payloads.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from django.conf import settings
from django.utils.translation import gettext as _

from libs.crypto.rsa_utils import load_client_public_key
from libs.crypto.session_store import create_session
from libs.responses import error_response, success_response


class CryptoHandshakeView(APIView):
    """
    POST /api/v1/crypto/handshake
    Body: {"public_key": "<client RSA public key PEM>"}
    Resp: {"session_id", "key", "payload", "nonce", "expires_in"}
    """

    authentication_classes = []  # Handshake must work pre-auth
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "crypto_handshake"  # limit abuse (session + RSA CPU cost)
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["Crypto"],
        request={"application/json": {"type": "object", "properties": {
            "public_key": {"type": "string", "description": "Client RSA public key (PEM)"},
        }}},
        responses={200: dict, 400: dict},
    )
    def post(self, request):
        public_key_pem = (request.data or {}).get("public_key")
        if not public_key_pem or "BEGIN PUBLIC KEY" not in str(public_key_pem):
            return error_response(
                message=_("Missing or invalid 'public_key' (RSA PEM required)"),
                status=400,
            )

        try:
            client_key = load_client_public_key(str(public_key_pem))
        except Exception:
            return error_response(message=_("Invalid client public key"), status=400)

        session = create_session(
            client_public_key_pem=str(public_key_pem),
            ttl=settings.CRYPTO_SESSION_TTL,
        )
        return success_response(data=session, message=_("Handshake successful"))
