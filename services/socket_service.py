"""
Socket server service for managing WebSocket connections and real-time communication.
"""
import json
import logging
from typing import Any, Dict

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


class SocketService:
    """
    Service for managing WebSocket connections and real-time messaging.
    Provides methods to send messages to users, groups, or broadcast.
    """

    @staticmethod
    def send_to_user(user_id: str, event_type: str, data: Dict[str, Any]) -> None:
        """
        Send a real-time event to a specific user.
        """
        channel_layer = get_channel_layer()
        group_name = f"notifications_{user_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_notification",
                "data": {
                    "type": event_type,
                    "data": data,
                },
            },
        )
        logger.info(f"Sent {event_type} to user {user_id}")

    @staticmethod
    def send_to_group(group_name: str, event_type: str, data: Dict[str, Any]) -> None:
        """
        Send a real-time event to a group/channel.
        """
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "send_notification",
                "data": {
                    "type": event_type,
                    "data": data,
                },
            },
        )
        logger.info(f"Sent {event_type} to group {group_name}")

    @staticmethod
    def broadcast(event_type: str, data: Dict[str, Any]) -> None:
        """
        Broadcast a real-time event to all connected users.
        Note: This requires a global broadcast group.
        """
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "broadcast",
            {
                "type": "send_notification",
                "data": {
                    "type": event_type,
                    "data": data,
                },
            },
        )
        logger.info(f"Broadcast {event_type} to all users")