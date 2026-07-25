import json

from channels.generic.websocket import AsyncWebsocketConsumer


class NotificationConsumer(AsyncWebsocketConsumer):
    """Real-time notification consumer."""

    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
        else:
            self.group_name = f"notifications_{self.user.id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (TypeError, ValueError):
            await self.send(text_data=json.dumps({"type": "error", "detail": "Invalid JSON"}))
            return
        # Handle incoming WebSocket messages
        message_type = data.get("type", "")
        if message_type == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))

    async def send_notification(self, event):
        """Send notification to WebSocket."""
        await self.send(text_data=json.dumps(event["data"]))


class ChatConsumer(AsyncWebsocketConsumer):
    """Real-time chat consumer."""

    async def connect(self):
        self.user = self.scope["user"]
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"chat_{self.room_id}"

        if self.user.is_anonymous:
            await self.close()
        else:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (TypeError, ValueError):
            await self.send(text_data=json.dumps({"type": "error", "detail": "Invalid JSON"}))
            return
        message = {
            "type": "chat_message",
            "user_id": str(self.user.id),
            "user_name": self.user.full_name,
            "message": data.get("message", ""),
        }
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "chat.message", "data": message},
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["data"]))