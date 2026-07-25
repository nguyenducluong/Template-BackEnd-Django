from django.urls import path

from apps.api.crypto_views import CryptoHandshakeView

app_name = "crypto"

urlpatterns = [
    path("handshake/", CryptoHandshakeView.as_view(), name="handshake"),
]

