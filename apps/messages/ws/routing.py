"""Route socket cua app messages (duoc gateway websocket gom lai)."""

from django.urls import re_path

from .consumers import ChatConsumer

messages_websocket_urlpatterns = [
	re_path(r'ws/chat/(?P<room_id>[\w-]+)/$', ChatConsumer.as_asgi()),
]
