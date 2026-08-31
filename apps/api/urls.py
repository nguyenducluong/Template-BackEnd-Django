from django.urls import include, path

app_name = "api-v1"

urlpatterns = [
    path("accounts/", include("apps.accounts.urls")),
    path("info/", include("apps.info.urls")),
    path("face/", include("apps.face.urls")),
    path("ai/", include("apps.ai.urls")),
    path("crypto/", include("apps.api.crypto_urls")),
    path("health/", include("apps.api.health_urls")),
]

