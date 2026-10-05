"""
WebSocket URL routing — GATEWAY gom route tu cac app nghiep vu.

Quy tac:
	- File nay KHONG khai consumer truc tiep (tru NotificationConsumer ha tang).
	- App nao can realtime thi tao <app>/ws/routing.py roi import vao day.
	- Hien tai: notifications (ha tang) + chat (app messages).

DAU '/' DAU TIEN: KHONG duoc them vao regex. `channels.routing.URLRouter` tu
cat dau '/' o `scope['path']` truoc khi doi chieu (da xac nhan qua log uvicorn:
"No route found for path 'ws/chat/<uuid>/'"). Regex co '^/' se khong bao gio
match path da bi cat do.
"""
from django.urls import re_path

from apps.messages.ws.routing import messages_websocket_urlpatterns

from . import consumers

websocket_urlpatterns = [
	re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
	*messages_websocket_urlpatterns,
]