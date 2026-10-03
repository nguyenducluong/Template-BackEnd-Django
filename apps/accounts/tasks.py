"""
Celery tasks của app accounts.

Đăng ký định kỳ trong ``CELERY_BEAT_SCHEDULE`` (config/settings/base.py).
Chạy worker + beat:
    celery -A config.celery worker --loglevel=info
    celery -A config.celery beat --loglevel=info
"""

import logging

from celery import shared_task

logger = logging.getLogger("apps")


@shared_task(name="accounts.purge_expired_jwt_blacklist")
def purge_expired_jwt_blacklist() -> int:
    """Xóa các JTI đã hết hạn khỏi bảng JWT blacklist.

    Bảng ``_0041_jwt_blacklist`` là nguồn sự thật cho việc thu hồi token
    (logout / rotation refresh token). Nếu không có job dọn định kỳ, bảng sẽ
    phình mãi vì mỗi lần logout lại thêm 1 dòng.

    Returns:
        Số bản ghi đã xóa.
    """
    from apps.accounts.models import JWTBlacklist

    deleted = JWTBlacklist.purge_expired()
    logger.info("JWT blacklist: đã dọn %s bản ghi hết hạn", deleted)
    return deleted


@shared_task(name="accounts.purge_expired_refresh_sessions")
def purge_expired_refresh_sessions() -> int:
    """Dọn các phiên refresh token đã hết hạn từ lâu.

    Bảng ``_0042_refresh_token_session` tăng 1 dòng mỗi lần refresh, và mỗi
    phiên sinh ra hàng chục dòng (chuỗi xoay token). Không có job dọn thì bảng
    phình vô hạn và mọi truy vấn "list phiên" đều phải quét nhiều dòng chết.

    KHÔNG xoá ngay khi hết hạn: giữ ``REFRESH_SESSION_KEEP_DAYS`` ngày để còn
    đối chiếu được với log khi điều tra sự cố (spec §55).
    """
    from django.conf import settings

    from apps.accounts.models import RefreshTokenSession

    keep_days = int(getattr(settings, "REFRESH_SESSION_KEEP_DAYS", 30))
    deleted = RefreshTokenSession.purge_expired(keep_days=keep_days)
    logger.info("Refresh sessions: đã dọn %s bản ghi quá %s ngày", deleted, keep_days)
    return deleted
