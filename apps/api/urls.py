from django.urls import include, path

from apps.api.default_views import GetRegisteredSystemsView
from apps.api.system_config_views import GetSystemsConfigView

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
    # ---- Port từ Laravel API cũ (giữ nguyên path để frontend STD ít phải đổi) ----
    path("define/", include("apps.api.define_urls")),
    path("default/get_systems", GetRegisteredSystemsView.as_view(), name="default-get-systems"),
    path("system/get_systems_config", GetSystemsConfigView.as_view(), name="system-get-systems-config"),
]

