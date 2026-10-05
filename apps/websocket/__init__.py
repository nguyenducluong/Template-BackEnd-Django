"""
Socket gateway chung — KHÔNG chứa nghiệp vụ của app nào.

Vai trò của app `websocket`:
    - Cung cấp `BaseConsumer` (xác thực, envelope, ping/pong, mã lỗi chuẩn)
      để mọi app khác (messages, face, systems...) kế thừa.
    - Cung cấp `registry` (quy ước tên group + hàm push) để code SYNC
      (views/services/tasks) bắn event realtime.
    - Gom route socket của các app trong `routing.py`.

Quy ước envelope (áp cho MỌI consumer):
    FE -> BE: {"type": "<domain>.<action>", "request_id": "<uuid>", "data": {...}}
    BE -> FE: {"type": "event", "event": "<domain>.<event>", "data": {...}}
    BE -> FE: {"type": "error", "code": "<CODE>", "detail": "...", "request_id": "..."}

Mã lỗi socket chuẩn:
    UNAUTHENTICATED — chưa đăng nhập (đáng lẽ middleware đã chặn)
    NOT_MEMBER      — không phải member của room (room kín)
    FORBIDDEN       — là member nhưng thiếu quyền (vd chỉ admin)
    BAD_PAYLOAD     — JSON sai / thiếu trường
    NOT_FOUND       — room/resource không tồn tại (hoặc đã giải tán)
    RATE_LIMITED    — gửi quá nhanh
"""

# Websocket application - real-time communication gateway

