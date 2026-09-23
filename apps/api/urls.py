from django.urls import include, path

app_name = "api-v1"

# Quy ước URL: KHÔNG có trailing slash (APPEND_SLASH=False trong settings).
# Prefix include giữ "/" cuối (cấu trúc của Django), path con không "/" cuối.
urlpatterns = [
    path("accounts/", include("apps.accounts.urls")),
    path("info/", include("apps.info.urls")),
    path("face/", include("apps.face.urls")),
    path("ai/", include("apps.ai.urls")),
    path("systems/", include("apps.systems.urls")),
    path("crypto/", include("apps.api.crypto_urls")),
    path("health/", include("apps.api.health_urls")),
]

