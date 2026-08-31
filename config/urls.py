"""
Main URL configuration.
API versioning is done via URL path prefix (/api/v1/, /api/v2/).
"""
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView


def _api_envelope(status_code, message):
    return JsonResponse({
        "success": False,
        "data": None,
        "message": message,
        "errors": {"detail": [message]},
        "meta": {"status_code": status_code},
    }, status=status_code)


def api_page_not_found(request, exception=None):
    """Return the standard envelope for unknown /api/ URLs instead of HTML."""
    if request.path.startswith("/api/"):
        return _api_envelope(404, "Resource not found")
    from django.views import defaults
    return defaults.page_not_found(request, exception)


def api_server_error(request):
    """Return the standard envelope for unhandled /api/ errors instead of HTML."""
    if request.path.startswith("/api/"):
        return _api_envelope(500, "Internal server error")
    from django.views import defaults
    return defaults.server_error(request)


handler404 = "config.urls.api_page_not_found"
handler500 = "config.urls.api_server_error"

urlpatterns = [
    # API Documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # API v1 - tất cả apps đều đi qua đây
    path("api/v1/", include("apps.api.urls")),
]

# Debug toolbar
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path("__debug__/", include(debug_toolbar.urls)),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)