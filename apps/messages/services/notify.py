"""Ban event realtime cho app messages qua gateway websocket."""

from apps.websocket import registry


def notify_room(room_id, event, data, request_id='') -> None:
	"""Ban event toi toan bo member dang mo room."""
	registry.push_to_room(room_id, event, data, request_id)


def notify_user(user_id, event, data, request_id='') -> None:
	"""Ban event toi socket thong bao rieng cua 1 user."""
	registry.push_to_user(user_id, event, data, request_id)


def notify_users(user_ids, event, data, request_id='') -> None:
	"""Ban event toi nhieu user (gom san 1 danh sach id de fan-out nhanh)."""
	for user_id in user_ids:
		notify_user(user_id, event, data, request_id)
