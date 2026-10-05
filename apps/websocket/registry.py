"""
Registry socket — quy ước tên group + hàm push cho code SYNC.

Mọi app nghiệp vụ (messages, face, systems...) gọi các hàm ở đây để bắn
event realtime, KHÔNG tự gọi channel_layer.group_send rời rạc.

Quy tắc tên group (BẮT BUỘC):
    channels_redis chỉ nhận tên gồm ASCII alphanumerics và `-`, `_`, `.`.
    Dấu `:` sẽ làm raise:
        TypeError: Group name must be a valid unicode string ... only ASCII
        alphanumerics, hyphens, underscores, or periods
    ⇒ Ở ĐÂY dùng `-` làm dấu phân tách. Các app khác (face, systems...) cũng
    phải theo đúng quy tắc này, nếu không mọi consumer sẽ fail khi group_add.

Quy ước tên group (tránh đụng nhau giữa các app):
    user-{user_id}   — socket thông báo riêng của 1 user
    room-{uuid}      — room chat kín của app messages
    broadcast        — phát cho toàn bộ client (hạn chế dùng)
    <app>-<scope>    — app khác tự đặt theo tiền tố của mình
                      (vd face-attendance, systems-approval-<id>)
"""

import datetime
import decimal
import logging
import uuid
from typing import Any, Dict

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def json_safe(value: Any) -> Any:
    """Ép mọi kiểu "lạ" (UUID, datetime, Decimal…) về dạng JSON serialize được.

    VÌ SAO CẦN: channel layer dùng JSON serializer riêng, KHÔNG có JSONEncoder
    mặc định của Django/DRF. Payload chứa `uuid.UUID` sẽ làm nó ném
    `TypeError: can not serialize 'UUID' object` ⇒ exception nổi lên consumer ⇒
    consumer chết ⇒ socket của client bị ngắt.

    Đây là CHỐT CHẶN CUỐI cho MỌI app dùng websocket (messages, face,
    systems…), nên không app nào phải tự nhớ ép kiểu.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return str(value)


def user_group(user_id) -> str:
	"""Tên group thông báo riêng của 1 user."""
	return f'user-{user_id}'


def room_group(room_id) -> str:
	"""Tên group room chat kín (app messages)."""
	return f'room-{room_id}'


def _push(group_name: str, event: str, data: Dict[str, Any], request_id: str = '') -> None:
	channel_layer = get_channel_layer()
	async_to_sync(channel_layer.group_send)(
		group_name,
		{'type': 'fan.out', 'event': event, 'data': json_safe(data or {}), 'request_id': request_id or ''},
	)
	logger.info('Socket push %s -> %s', event, group_name)


def push_to_user(user_id, event: str, data: Dict[str, Any], request_id: str = '') -> None:
	"""Bắn event tới socket thông báo riêng của 1 user."""
	_push(user_group(user_id), event, data, request_id)


def push_to_room(room_id, event: str, data: Dict[str, Any], request_id: str = '') -> None:
	"""Bắn event tới toàn bộ member đang mở room chat."""
	_push(room_group(room_id), event, data, request_id)


def push_broadcast(event: str, data: Dict[str, Any], request_id: str = '') -> None:
	"""Phát event cho toàn bộ client (chỉ dùng cho thông báo hệ thống)."""
	_push('broadcast', event, data, request_id)
