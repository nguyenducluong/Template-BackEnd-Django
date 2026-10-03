"""Service quản lý phiên đăng nhập (spec §45, §19).

Endpoint này CHỈ trả metadata để người dùng nhận ra thiết bị của mình.

KHÔNG BAO GIỜ trả:
  - `token_hash` (bí mật của hệ thống)
  - refresh token dạng bất kỳ
  - `family_id` trần cho client (chỉ dùng nội bộ để thu hồi cả nhóm)
"""
from django.utils import timezone


def _describe(user_agent: str) -> str:
    """Rút gọn User-Agent thành nhãn thiết bị dễ đọc.

    Chỉ để HIỂN THỊ. Không dùng làm định danh bảo mật (spec §74: device name
    do client gửi lên không được tin).
    """
    if not user_agent:
        return "Unknown device"
    agent = user_agent.lower()
    for needle, label in (("edg/", "Microsoft Edge"), ("chrome/", "Google Chrome"), ("firefox/", "Mozilla Firefox"), ("safari/", "Safari")):
        if needle in agent:
            return label
    if "mobile" in agent or "android" in agent or "iphone" in agent:
        return "Mobile device"
    return "Other browser"


def list_sessions(user, current_session_id=None) -> list:
    """Danh sách phiên đang hoạt động của user, mới nhất trước."""
    from apps.accounts.models import RefreshTokenSession

    now = timezone.now()
    rows = (
        RefreshTokenSession.active_for_user(user)
        .filter(expires_at__gt=now, absolute_expires_at__gt=now)
        .order_by("-last_used_at")
        .only("id", "user_agent", "ip_address", "crt_at", "last_used_at", "expires_at")
    )

    result = []
    for row in rows:
        last_used = row.last_used_at or row.crt_at
        result.append(
            {
                "id": str(row.id),
                "device": _describe(row.user_agent),
                "user_agent": row.user_agent[:160],
                "ip_address": row.ip_address,
                "created_at": row.crt_at,
                "last_used_at": last_used,
                "expires_at": row.expires_at,
                # True cho thiết bị đang gọi API ⇒ FE đánh dấu "Current device".
                "current": bool(current_session_id) and str(row.id) == str(current_session_id),
            }
        )
    return result


def get_current_session_id(request) -> str | None:
    """Lấy `sid` từ access token để đánh dấu phiên hiện tại.

    `sid` do `refresh_tokens.rotate()` nhúng vào access token (spec §46).
    Không decode lại token ở đây — DRF đã gắn `request.auth` = payload.
    """
    payload = getattr(request, "auth", None)
    if isinstance(payload, dict):
        return payload.get("sid")
    return None


def humanize_last_used(last_used_at) -> str:
    """Mô tả thời điểm dùng gần nhất theo giờ tương đối."""
    if not last_used_at:
        return "Never"
    delta = timezone.now() - last_used_at
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60} minute(s) ago"
    if seconds < 86400:
        return f"{seconds // 3600} hour(s) ago"
    return f"{seconds // 86400} day(s) ago"