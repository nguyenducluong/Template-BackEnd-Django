"""Service đăng nhập: tạo phiên refresh MỚI mỗi lần login.

Mỗi lần login = 1 family mới (spec §6). Đây là nơi duy nhất gọi
`create_session` mà không có `parent`, tức là mở đầu một chuỗi token mới —
giữ cho mỗi thiết bị một family độc lập (INVARIANT 7).
"""
import logging

from django.db import transaction

from libs.auth import refresh_tokens as rt

logger = logging.getLogger("apps")


class AuthService:
    """Orchestration cho đăng nhập / đăng xuất."""

    # Phải atomic trên ĐÚNG alias (`schema_user`) — xem `rt.session_db_alias()`.
    # `atomic` không tham số sẽ mở trên `default` trong khi query chạy trên
    # `schema_user` ⇒ transaction không bao phủ thật sự.
    @staticmethod
    @transaction.atomic(using=rt.session_db_alias())
    def login(user, request=None) -> dict:
        """Đăng nhập: cấp access token + mở family refresh mới.

        Returns::

            {"access": str, "refresh": str, "session": RefreshTokenSession}
        """
        from libs.auth.jwt_utils import generate_access_token

        raw_refresh, session = rt.create_session(user, request=request)
        access = generate_access_token(user, sid=str(session.id))
        logger.info("AUTH_LOGIN_SUCCESS: user=%s family=%s ip=%s", user.id, session.family_id, session.ip_address)
        return {"access": access, "refresh": raw_refresh, "session": session}

    @staticmethod
    def logout(raw_refresh_token, user=None) -> bool:
        """Đăng xuất 1 thiết bị: thu hồi phiên của token đó. Trả `True` nếu có.

        Idempotent (spec §17): token không tồn tại / đã thu hồi vẫn trả
        success, để client logout không bị kẹt vì token đã chết.
        """
        if not raw_refresh_token:
            return False

        # Token OPAQUE (tiền tố `rt_`) ⇒ thu hồi đúng phiên tương ứng.
        # Không dùng `rotate()` ở đây: logout không được sinh token mới.
        if str(raw_refresh_token).startswith(rt.TOKEN_PREFIX):
            try:
                session = rt._resolve_session(raw_refresh_token)
            except rt.RefreshTokenError:
                # Token không hợp lệ / không còn trong DB → coi như đã đăng xuất.
                return False
            # Chỉ thu hồi phiên của chính token này, KHÔNG đụng family khác
            # (INVARIANT 8: logout 1 thiết bị không ảnh hưởng thiết bị khác).
            rt.revoke_session(session)
            logger.info("AUTH_LOGOUT: user=%s session=%s", session.user_id, session.id)
            return True

        # Token JWT CŨ (trước khi lên Token Family): không có bản ghi session, nên
        # phải thu hồi bằng cơ chế blacklist cũ. Nếu bỏ qua nhánh này, logout
        # sẽ chỉ xoá token ở client còn server vẫn cấp được phiên mới từ token đó —
        # tức "đăng xuất" nhưng phiên vẫn sống.
        from libs.auth.jwt_utils import blacklist_token

        blacklist_token(raw_refresh_token)
        logger.info("AUTH_LOGOUT (legacy jwt): jti thu hồi")
        return True

    @staticmethod
    def logout_all(user) -> int:
        """Đăng xuất mọi thiết bị (INVARIANT 9)."""
        count = rt.revoke_all_for_user(user)
        logger.info("AUTH_LOGOUT_ALL: user=%s — đã thu hồi %s phiên", user.id, count)
        return count

    @staticmethod
    def revoke_session(user, session_id) -> bool:
        """Thu hồi 1 phiên cụ thể. Chỉ chủ phiên mới được thu hồi (spec §20).

        Trả False nếu không tìm thấy HOẶC phiên thuộc user khác — hai trường
        hợp này cùng trả False để không lộ ra sự tồn tại của phiên người khác.
        """
        from apps.accounts.models import RefreshTokenSession

        session = RefreshTokenSession.objects.filter(id=session_id, user=user).first()
        if session is None:
            return False
        rt.revoke_session(session)
        logger.info("AUTH_SESSION_REVOKED: user=%s session=%s", user.id, session_id)
        return True