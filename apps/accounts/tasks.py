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
