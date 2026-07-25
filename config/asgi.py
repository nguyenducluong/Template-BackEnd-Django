"""
ASGI config for the project.
Supports both HTTP (Django) and WebSocket (Channels) protocols.
WebSocket authentication is handled by our custom JWTAuthMiddleware
(replacing channels.auth.AuthMiddlewareStack which depended on
django.contrib.sessions + django.contrib.auth).
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa

from apps.websocket.routing import websocket_urlpatterns  # noqa
from libs.auth.jwt_middleware import JWTAuthMiddlewareStack  # noqa

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})