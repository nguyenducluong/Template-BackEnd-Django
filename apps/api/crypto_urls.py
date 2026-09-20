from django.urls import path

from apps.api.crypto_views import CryptoHandshakeView, ServerPublicKeyView

app_name = "crypto"

urlpatterns = [
    # GET: RSA public key của server — client dùng để mã hóa REQUEST
    path("public_key", ServerPublicKeyView.as_view(), name="public-key"),
    # POST: handshake — client gửi client_public_key (đã mã hóa), nhận session_id
    # + encrypt_request → công tắc bật/tắt mã hóa cho các API sau
    path("handshake", CryptoHandshakeView.as_view(), name="handshake"),
]