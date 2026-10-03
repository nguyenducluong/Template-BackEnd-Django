"""Refresh token OPAQUE + Token Family + Rotation + Reuse Detection.

Vì sao KHÔNG dùng JWT cho refresh token:
  - JWT tự chứa thông tin ⇒ ai đọc token cũng thấy user_id, jti...
  - Token KHÔNG THỦ TỊCH: huỷ token phải tra cứu server mỗi lần.
  - Quan trọng nhất: reuse detection cần biết token THUỘC CHUỖI nào, và điều
    đó phải nằm trong DB chứ không nằm trong token (token có thể bị sao chép và
    gửi lại bất cứ lúc nào).

Opaque token = chuỗi ngẫu nhiên từ CSPRNG. DB chỉ lưu HMAC-SHA256 của nó:
  - Token rò trong log/backup ⇒ kẻ tấn công KHÔNG dựng lại được token hợp lệ,
    vì HMAC cần SECRET_KEY nằm trong biến môi trường.
  - Tra cứu bằng index thường (không cần hash chậm như bcrypt).

Mô hình xoay token (chuẩn OAuth 2.0 Security BCP):

    login          F1/RT1(active)
    refresh(RT1)   -> RT1.revoked, replaced_by=RT2; RT2(active, family F1)
    refresh(RT1)   -> REUSE! -> thu hồi CẢ family F1 -> 401
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import timedelta
from typing import Any, Dict

from django.conf import settings
from django.db import DEFAULT_DB_ALIAS, router, transaction
from django.utils import timezone

logger = logging.getLogger("apps")

# Tiền tố refresh token: giúp phân biệt ngay với access token khi đọc log.
TOKEN_PREFIX = "rt_"

# Entropy: 48 byte = 384 bit, rất dư so với ngưỡng 128 bit của OWASP.
TOKEN_BYTES = 48


# ---------------------------------------------------------------------------
# Lỗi nghiệp vụ
# ---------------------------------------------------------------------------

class RefreshTokenError(Exception):
    """Base cho mọi lỗi của luồng refresh token."""

    # Mã trả về cho FE (spec §25): FE dựa vào MÃ để biết có nên retry hay phải
    # đăng nhập lại, thay vì đoán qua câu chữ message (có bản dịch, không ổn định).
    code = "AUTH_REFRESH_TOKEN_INVALID"
    status_code = 401


class RefreshTokenMissing(RefreshTokenError):
    code = "AUTH_REFRESH_TOKEN_MISSING"


class RefreshTokenInvalid(RefreshTokenError):
    code = "AUTH_REFRESH_TOKEN_INVALID"


class RefreshTokenRevoked(RefreshTokenError):
    """Token bị thu hồi có chủ đích (logout / đổi mật khẩu)."""

    code = "AUTH_REFRESH_TOKEN_REVOKED"


class RefreshTokenExpired(RefreshTokenError):
    code = "AUTH_REFRESH_TOKEN_EXPIRED"


class RefreshReuseDetected(RefreshTokenError):
    """Token đã bị xoay lại được gửi lên ⇒ khả năng token bị đánh cắp.

    Khác `RefreshTokenRevoked`: khi phát hiện reuse ta thu hồi TOÀN BỘ family,
    vì nếu chỉ thu hồi token này thì kẻ tấn công vẫn còn token khác trong
    chính chuỗi đó (spec §9).
    """

    code = "AUTH_REFRESH_REUSE_DETECTED"


# ---------------------------------------------------------------------------
# Sinh token + băm
# ---------------------------------------------------------------------------

def generate_raw_token() -> str:
    """Sinh refresh token opaque bằng CSPRNG.

    KHÔNG dùng `uuid4().hex` (spec §35): uuid4 chỉ 122 bit entropy. `secrets`
    là nguồn entropy chuẩn của OS.
    """
    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(TOKEN_BYTES)}"


def hash_token(raw_token: str) -> str:
    """HMAC-SHA256 của refresh token, dùng làm khóa tra cứu trong DB.

    HMAC chứ không phải SHA-256 thuần: nếu attacker có dump DB thì với SHA-256
    thuần họ brute-force offline được; với HMAC thì phải có `SECRET_KEY` của
    server. HMAC cũng rẻ hơn nhiều so với bcrypt/argon2 — chấp nhận được vì
    token là random 384 bit (đoán brute-force vô nghĩa), mục tiêu chỉ là lookup
    nhanh + không lưu plaintext (spec §34).
    """
    secret = str(settings.SECRET_KEY).encode("utf-8")
    return hmac.new(secret, str(raw_token or "").encode("utf-8"), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

def _idle_seconds() -> int:
    """Thời gian nhàn rỗi tối đa (không hoạt động bao lâu thì hết phiên)."""
    fallback = 7 * 24 * 3600
    try:
        return max(int(getattr(settings, "REFRESH_IDLE_SECONDS", fallback)), 60)
    except (TypeError, ValueError):
        return fallback


def _absolute_seconds() -> int:
    """Thời gian sống tối đa của cả phiên, tính từ lúc login."""
    fallback = 30 * 24 * 3600
    try:
        return max(int(getattr(settings, "REFRESH_ABSOLUTE_SECONDS", fallback)), 60)
    except (TypeError, ValueError):
        return fallback


# ---------------------------------------------------------------------------
# Tạo / thu hồi session
# ---------------------------------------------------------------------------

def _client_meta(request=None) -> Dict[str, Any]:
    """Metadata thiết bị từ request (chỉ để hiển thị, KHÔNG phải bảo mật)."""
    meta = {"user_agent": "", "ip_address": None, "device_name": ""}
    if request is None:
        return meta
    try:
        agent = request.META.get("HTTP_USER_AGENT", "") or ""
        meta["user_agent"] = agent[:255]
        meta["device_name"] = agent[:120]
    except Exception:  # noqa: BLE001 — metadata lỗi không được làm hỏng đăng nhập
        pass
    try:
        from libs.network import get_client_ip

        meta["ip_address"] = get_client_ip(request)
    except Exception:  # noqa: BLE001
        pass
    return meta


def create_session(user, request=None, family_id=None, parent=None):
    """Tạo MỘT phiên refresh mới, trả ``(raw_token, session)``.

    `family_id=None` ⇒ bắt đầu family MỚI (dùng lúc login).
    Truyền `family_id` ⇒ nối vào family hiện có (dùng lúc xoay token).
    """
    from apps.accounts.models import RefreshTokenSession

    now = timezone.now()
    family = family_id or uuid.uuid4()
    meta = _client_meta(request)

    # `absolute_expires_at` KHÔNG reset khi xoay — token kế thừa thì giữ mốc
    # của family (spec §38), nên lấy từ `parent`; token đầu tiên thì bắt đầu
    # từ `now`.
    absolute_expires = parent.absolute_expires_at if parent is not None else now + timedelta(seconds=_absolute_seconds())

    raw_token = generate_raw_token()
    session = RefreshTokenSession.objects.create(
        user=user,
        family_id=family,
        token_hash=hash_token(raw_token),
        parent=parent,
        expires_at=now + timedelta(seconds=_idle_seconds()),
        absolute_expires_at=absolute_expires,
        last_used_at=now,
        **meta,
    )
    return raw_token, session


def revoke_session(session, now=None) -> None:
    """Thu hồi MỘT phiên (logout thiết bị hiện tại)."""
    if session.revoked_at is None:
        session.revoked_at = now or timezone.now()
        session.save(update_fields=["revoked_at", "upd_at"])


def revoke_family(family_id, now=None) -> int:
    """Thu hồi TOÀN BỘ token trong một family. Trả số bản ghi bị thu hồi."""
    from apps.accounts.models import RefreshTokenSession

    now = now or timezone.now()
    # Chỉ chạm bản ghi CÒN active — bản ghi đã thu hồi giữ nguyên `revoked_at`
    # cũ để không mất dấu vết thời điểm xoay (phục vụ audit).
    affected = RefreshTokenSession.objects.filter(family_id=family_id, revoked_at__isnull=True).update(revoked_at=now)
    if affected:
        logger.info("Đã thu hồi family %s: %s phiên", family_id, affected)
    return affected


def revoke_all_for_user(user, now=None) -> int:
    """Thu hồi mọi phiên của user (logout-all / đổi mật khẩu)."""
    from apps.accounts.models import RefreshTokenSession

    now = now or timezone.now()
    return RefreshTokenSession.active_for_user(user).update(revoked_at=now)


# ---------------------------------------------------------------------------
# Tra cứu + phân nhánh trạng thái
# ---------------------------------------------------------------------------

def session_db_alias() -> str:
    """Alias DB nơi `RefreshTokenSession` thực sự được lưu.

    VÌ SAO CẦN (bug thật đã xảy ra): dự án chạy PostgreSQL multi-schema, mỗi
    schema là một connection riêng (`schema_user`, `schema_info`, ...). Lệnh
    `transaction.atomic()` KHÔNG có tham số sẽ mở transaction trên
    `DEFAULT_DB_ALIAS` (`default`), trong khi query lại chạy trên `schema_user`.

    Hậu quả nếu không sửa: `select_for_update()` ném
        TransactionManagementError: select_for_update cannot be used
        outside of a transaction
    tức toàn bộ cơ chế **khoá dòng chống race khi xoay token** — phần cốt
    lõi của Token Family — KHÔNG hoạt động trên môi trường thật (chỉ "chạy"
    trong test vì test gom mọi schema về `public`).
    """
    from apps.accounts.models import RefreshTokenSession

    return router.db_for_write(RefreshTokenSession) or DEFAULT_DB_ALIAS


def _resolve_session(raw_token: str, lock: bool = False):
    """Tìm session từ token gốc. Ném lỗi nếu token thiếu/sai định dạng."""
    if not raw_token:
        raise RefreshTokenMissing()
    # Lọc theo tiền tố TRƯỚC khi băm: token không có tiền tố `rt_` không thể
    # do hệ thống này cấp ⇒ coi như không hợp lệ, tiết kiệm 1 lần HMAC.
    if not str(raw_token).startswith(TOKEN_PREFIX):
        raise RefreshTokenInvalid()
    from apps.accounts.models import RefreshTokenSession

    queryset = RefreshTokenSession.objects.select_related("user")
    if lock:
        # `select_for_update()` ⇒ PostgreSQL khoá dòng, chặn 2 request refresh
        # song song cùng 1 token (spec §14). KHÔNG dùng được ngoài transaction.
        queryset = queryset.select_for_update()
    session = queryset.filter(token_hash=hash_token(raw_token)).first()
    if session is None:
        raise RefreshTokenInvalid()
    return session


def _check_state(session) -> None:
    """Phân nhánh trạng thái ⇒ ném lỗi tương ứng. Trả về None nếu hợp lệ.

    Đây là phần CỐT LÕI của reuse detection. Điều kiện phân biệt:

        revoked + có replaced_by  ⇒ token đã bị XOAY, giờ lại gửi lên
                                  ⇒ REUSE (khả năng bị đánh cắp)
        revoked + không replaced_by ⇒ bị thu hồi có chủ đích (logout,
                                  đổi mật khẩu) ⇒ KHÔNG tính là reuse

    VÌ SAO KHÔNG DÙNG "KHOẢNG ÂN HẠN THEO THỜI GIAN" (cách cũ, grace 60s):
    Thời gian không phản ánh ý định. Client hợp lệ gửi lại token cũ chỉ khi
    response trước bị mất; kẻ tấn công thì gửi bất cứ lúc nào. Phân biệt bằng
    TRẠNG THÁI thì đúng trong mọi trường hợp — kể cả client quay lại app sau
    5 phút, đúng nguyên nhân gốc của lỗi "token 7 ngày bị blacklist oan".
    """
    if session.revoked_at is not None:
        if session.was_rotated:
            raise RefreshReuseDetected()
        raise RefreshTokenRevoked()

    now = timezone.now()
    if session.absolute_expires_at <= now or session.expires_at <= now:
        raise RefreshTokenExpired()


# ---------------------------------------------------------------------------
# Rotate
# ---------------------------------------------------------------------------

def rotate(raw_token: str, request=None) -> Dict[str, Any]:
    """Xoay refresh token: cấu token mới, thu hồi token cũ. Trả session mới.

    Luồng (spec §13, §70):
        1. Hash token → tra session (khoá dòng)
        2. Kiểm tra trạng thái
        3. Tạo token mới CÙNG family
        4. Đánh dấu token cũ revoked + replaced_by
        5. Trả token mới

    Toàn bộ (3) và (4) nằm trong MỘT transaction: nếu tạo token mới xong mà
    đánh dấu token cũ thất bại thì sẽ có 2 token cùng active — vi phạm
    INVARIANT 1 (mỗi token chỉ dùng được 1 lần).

    Raises:
        RefreshReuseDetected | RefreshTokenRevoked | RefreshTokenExpired |
        RefreshTokenInvalid | RefreshTokenMissing
    """
    from libs.auth.jwt_utils import generate_access_token

    # Phải mở transaction trên ĐÚNG alias (`schema_user`), không phải `default`
    # — xem `session_db_alias()`. Nếu không, `select_for_update` bên dưới ném
    # TransactionManagementError ⇒ mất hoàn toàn khoá chống race.
    with transaction.atomic(using=session_db_alias()):
        session = _resolve_session(raw_token, lock=True)

        # Phát hiện TÁI SỬ DỤNG: nhớ family ra biến, để ra khỏi transaction rồi mới
        # thu hồi.
        #
        # VÌ SAO KHÔNG thu hồi ngay tại đây: `raise` sẽ ROLLBACK toàn bộ
        # transaction, kéo theo lệnh `revoke_family` vừa ghi ⇒ người dùng hợp lệ
        # vẫn giữ được phiên (đúng cái ta cần chặn). Nên thu hồi phải nằm NGOÀI
        # transaction, sau khi nó đã kết thúc.
        reuse_family = None
        try:
            _check_state(session)
        except RefreshReuseDetected:
            reuse_family = session.family_id
            session_data = {
                "user_id": session.user_id,
                "family_id": session.family_id,
                "session_id": session.id,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
            }

        if reuse_family is None:
            user = session.user
            if not getattr(user, "is_active", True):
                # Tài khoản bị khoá trong lúc phiên còn sống. `raise` bên dưới sẽ
                # rollback transaction ⇒ việc thu hồi family được ghi SAU, ở
                # ngoài transaction (giống nhánh reuse).
                inactive_family = session.family_id
                user = None
            else:
                # Tạo token mới TRƯỚC rồi mới thu hồi token cũ: `replaced_by` cần
                # id của token mới, mà id chỉ có sau khi tạo.
                new_raw, new_session = create_session(user, request=request, family_id=session.family_id, parent=session)

                now = timezone.now()
                session.revoked_at = now
                session.replaced_by = new_session
                session.last_used_at = now
                session.save(update_fields=["revoked_at", "replaced_by", "last_used_at", "upd_at"])

                # Access token mang `sid` = id phiên MỚI ⇒ khi điều tra sự cố có
                # thể biết chính xác phiên nào đang bị dùng (spec §46).
                access_token = generate_access_token(user, sid=str(new_session.id))

    # ---- Ngoài transaction ----
    if reuse_family is not None:
        # INVARIANT 3 (spec §9): thu hồi CẢ family để token mới nhất chết theo.
        # Nếu chỉ từ chối token cũ thì kẻ trộm vẫn dùng được các token khác
        # trong chính chuỗi đó.
        affected = revoke_family(reuse_family)
        logger.warning(
            "AUTH_REFRESH_REUSE_DETECTED: user=%s family=%s session=%s ip=%s ua=%r — đã thu hồi %s phiên",
            session_data["user_id"],
            reuse_family,
            session_data["session_id"],
            session_data["ip_address"],
            (session_data["user_agent"] or "")[:80],
            affected,
        )
        raise RefreshReuseDetected()

    if user is None:
        revoke_family(inactive_family)
        raise RefreshTokenRevoked()

    logger.info(
        "Xoay refresh token: user=%s family=%s session %s -> %s",
        user.id,
        session.family_id,
        session.id,
        new_session.id,
    )
    return {"access_token": access_token, "refresh_token": new_raw, "session": new_session}


def rotate_legacy_jwt(raw_token: str, request=None) -> Dict[str, Any]:
    """Xoay token JWT CŨ (đã cấp trước khi lên Token Family) rồi chuyển sang opaque.

    VÌ SAO CẦN: khi deploy, mọi người dùng đang đăng nhập vẫn giữ refresh token
    kiểu JWT trong localStorage. Nếu `rotate()` từ chối thẳng, TẤT CẢ phiên đang
    chạy sẽ bị đăng xuất oan dù token còn hạn 7 ngày.

    Luồng chuyển tiếp:
        token JWT cũ -> kiểm tra hợp lệ (chưa bị thu hồi)
                       -> thu hồi chính token này (đúng INVARIANT 1)
                       -> cấp access token mới + refresh OPAQUE (mở family mới)

    Sau lần refresh đầu tiên, client đã giữ token opaque nên các lượt sau đi qua
    `rotate()` bình thường. Không cần migrate dữ liệu, không reset DB.

    Raises: RefreshTokenError nếu token JWT cũ sai / hết hạn / đã bị thu hồi.
    """
    import jwt as pyjwt

    from libs.auth.jwt_utils import (
        _decode,
        _resolve_user,
        blacklist_token,
        generate_access_token,
        is_token_blacklisted,
    )

    try:
        payload = _decode(raw_token)
    except pyjwt.PyJWTError as exc:
        raise RefreshTokenInvalid() from exc

    if payload.get("token_type") != "refresh":
        raise RefreshTokenInvalid()

    # Token JWT cũ đã bị thu hồi ở lần refresh trước (qua luồng cũ hoặc qua
    # chính hàm này) ⇒ không dùng lại được.
    jti = payload.get("jti")
    if jti and is_token_blacklisted(jti):
        raise RefreshTokenRevoked()

    user = _resolve_user(payload)

    # Thu hồi token cũ TRƯỚC khi cấp token mới — nếu không, token này dùng
    # lại được vô hạn lần (vi phạm INVARIANT 1).
    blacklist_token(raw_token)

    raw_new, session = create_session(user, request=request)
    access_new = generate_access_token(user, sid=str(session.id))

    logger.info("AUTH_LEGACY_TOKEN_MIGRATED: user=%s jti=%s -> session %s", user.id, jti, session.id)
    return {"access_token": access_new, "refresh_token": raw_new, "session": session}