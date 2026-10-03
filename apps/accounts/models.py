import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models

from apps.info.models import Organization, Shift
from libs.auth.password import check_password, make_password


class User(models.Model):
    """
    Custom user model matching ``_0010_user``.

    Login is performed via either ``gen_id`` (8-digit number) or ``knox_id``.
    """

    class StatusChoices(models.IntegerChoices):
        WAITING = 0, "Waiting"
        APPROVED = 1, "Approval"
        REJECTED = 2, "Reject"
        BLOCKED = 3, "Block"
        DELETED = 4, "Deleted"

    id = models.BigAutoField(primary_key=True)

    crt_at = models.DateTimeField(auto_now_add=True)
    upd_at = models.DateTimeField(auto_now=True)
    change_pw_at = models.DateTimeField(auto_now_add=True)

    org = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="users",
        db_column="org_id",
    )
    shift = models.ForeignKey(
        Shift,
        on_delete=models.PROTECT,
        related_name="users",
        db_column="shift_id",
    )

    gen_id = models.CharField(max_length=8, unique=True, db_index=True)
    knox_id = models.CharField(max_length=15, unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=50)
    status = models.PositiveSmallIntegerField(
        choices=StatusChoices.choices,
        default=StatusChoices.WAITING,
    )
    ip_remember = models.CharField(max_length=15, null=True, blank=True)
    password = models.CharField(
        max_length=128,
        help_text="Hashed password (PBKDF2-SHA256).",
    )

    # ---- Account lockout (Phase 1d) ----
    failed_login_attempts = models.PositiveSmallIntegerField(
        default=0, help_text="Count of consecutive failed login attempts."
    )
    locked_until = models.DateTimeField(
        null=True, blank=True,
        help_text="Account locked until this time (NULL = not locked).",
    )

    class Meta:
        db_table = "_0010_user"
        ordering = ["-crt_at"]

    def __str__(self):
        return self.gen_id

    # Backwards-compatible auth protocol (DRF permission classes)
    @property
    def is_authenticated(self) -> bool:
        """Return True -- required by DRF permission classes."""
        return True

    @property
    def is_anonymous(self) -> bool:
        """Return False -- this is a real user, not an anonymous one."""
        return False

    @property
    def is_active(self) -> bool:
        """Active = approved (lockout is checked separately via is_account_locked)."""
        return self.status == self.StatusChoices.APPROVED

    # Password helpers
    def set_password(self, raw_password: str) -> None:
        """Hash and store raw_password in self.password."""
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Verify raw_password against the stored hash."""
        return check_password(raw_password, self.password)

    # Password expiry / AD SSO helpers
    @property
    def keyCheck(self) -> int:
        """Return 1 if user is required to change password, 0 otherwise.

        Rules:
        - Users must change password every 90 days.
        - NOTE: AD SSO (SAML) users will be excluded once third-party SSO
          integration is implemented (user to be added later).
        """
        from datetime import timedelta
        from django.utils import timezone
        max_age_days = getattr(settings, "PASSWORD_MAX_AGE_DAYS", 90)
        if self.change_pw_at and (timezone.now() - self.change_pw_at) < timedelta(days=max_age_days):
            return 0
        return 1

    def is_password_expired(self) -> bool:
        """Return True if the user's password is past the allowed age."""
        return self.keyCheck == 1

    # Account lockout helpers
    def is_account_locked(self) -> bool:
        """Return True if account is currently locked."""
        from django.utils import timezone
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def record_failed_login(self) -> None:
        """Increment failed login attempts and lock if threshold exceeded.

        Uses a database-side ``F()`` expression so concurrent failed logins
        are all counted (a read-modify-write in Python would lose updates
        under concurrency and let an attacker keep guessing).
        """
        from django.conf import settings
        from django.db.models import F
        from django.utils import timezone

        max_attempts = getattr(settings, "ACCOUNT_LOCKOUT_MAX_ATTEMPTS", 5)
        lockout_minutes = getattr(settings, "ACCOUNT_LOCKOUT_MINUTES", 15)

        type(self).objects.filter(pk=self.pk).update(
            failed_login_attempts=F("failed_login_attempts") + 1,
            upd_at=timezone.now(),
        )
        self.refresh_from_db(fields=["failed_login_attempts"])

        if self.failed_login_attempts >= max_attempts and not self.is_account_locked():
            self.locked_until = timezone.now() + timezone.timedelta(minutes=lockout_minutes)
            self.save(update_fields=["locked_until", "upd_at"])

    def reset_failed_login(self) -> None:
        """Reset failed login attempts on successful login."""
        if self.failed_login_attempts > 0 or self.locked_until:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.save(update_fields=["failed_login_attempts", "locked_until", "upd_at"])

    # Convenience overrides
    def save(self, *args, **kwargs):
        """Hash the password on creation if not already hashed."""
        is_new = self._state.adding
        if is_new and self.password:
            if not self.password.startswith("pbkdf2_sha256$"):
                self.set_password(self.password)
        return super().save(*args, **kwargs)


class JWTBlacklist(models.Model):
    """Database-backed JWT token blacklist (Phase 1b).

    Stores revoked JTIs until expiry. Cache is used as fast-path;
    DB is the source of truth surviving Redis restarts.
    """

    jti = models.CharField(max_length=64, primary_key=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "_0041_jwt_blacklist"
        ordering = ["-created_at"]
        verbose_name = "JWT Blacklist Entry"
        verbose_name_plural = "JWT Blacklist Entries"

    def __str__(self):
        return self.jti

    @classmethod
    def purge_expired(cls) -> int:
        """Remove expired entries. Call from periodic task."""
        from django.utils import timezone
        deleted, _ = cls.objects.filter(expires_at__lt=timezone.now()).delete()
        return deleted


class RefreshTokenSession(models.Model):
    """Mỗi dòng = MỘT refresh token cụ thể của MỘT phiên/thiết bị.

    Mô hình Token Family + Rotation + Reuse Detection (chuẩn OAuth 2.0 BCP):

        Login  -> family F1, tạo RT1 (active)
        Refresh(RT1) -> RT1.revoked + replaced_by=RT2, tạo RT2 (active, cùng F1)
        Refresh(RT1) LẠI -> REUSE DETECTED -> revoke TOÀN BỘ family F1

    VÌ SAO LƯU SESSION THAY VÌ BLACKLIST:
    Blacklist chỉ trả lời "token này còn dùng được không", không biết token đó
    THUỘC CHUỖI nào. Muốn phát hiện tái sử dụng và huỷ cả nhóm thì bắt buộc
    phải biết quan hệ cha–con giữa các token — đó là `family_id` + `parent` +
    `replaced_by`.

    TOKEN LÀ OPAQUE, KHÔNG PHẢI JWT:
    `token_hash` lưu HMAC-SHA256 của token gốc. Nếu DB bị lấy (SQL injection,
    backup rò, nhân viên đọc trực tiếp) thì kẻ tấn công KHÔNG dựng lại được
    token dùng được, vì HMAC cần `SECRET_KEY` của server.

    TƯƠNG THÍCH NGƯỜC DÙNG: token JWT cũ (đã cấp trước khi deploy) không có
    bản ghi ở bảng này. `libs/auth/refresh_tokens.py` tự nhận diện và chuyển
    token đó sang luồng mới ở lần refresh kế tiếp ⇒ không phải reset DB, không
    phải buộc người dùng đăng nhập lại.
    """

    # ---- Định danh ----
    id = models.UUIDField(primary_key=True, editable=False, default=uuid.uuid4)

    # FK trỏ THẲNG model User của app này, KHÔNG dùng `settings.AUTH_USER_MODEL`.
    # Lý do: dự án cố ý KHÔNG khai AUTH_USER_MODEL (settings/base.py:547 —
    # "not a Django auth model"), nên `settings.AUTH_USER_MODEL` vẫn trỏ tới
    # `auth.User` của Django ⇒ FK sẽ tham chiếu sai bảng (`auth_user`) và
    # mọi truy vấn phiên sẽ hỏng.
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="refresh_sessions",
        db_index=True,
    )

    # Gom mọi token sinh ra trong cùng 1 phiên đăng nhập (1 thiết bị).
    # KHÔNG phải khóa chính — token hiện hành tra bằng `token_hash` (spec §73).
    family_id = models.UUIDField(db_index=True)

    # HMAC-SHA256 của token gốc. Unique ⇒ lookup O(1) theo index và chặn trùng.
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)

    # Chuỗi liên kết: RT1.parent=None -> RT2.parent=RT1 -> ...
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    # Token đã thay thế token này. Có giá trị ⇒ token này đã bị xoay.
    replaced_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="replaces",
    )

    # ---- Trạng thái ----
    # NULL = đang hoạt động. Có giá trị = đã thu hồi (xoay / logout / reuse).
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)

    last_used_at = models.DateTimeField(null=True, blank=True)

    # ---- Hạn dùng ----
    # Hết hạn IDLE: last_used_at + idle_seconds (không hoạt động 7 ngày → chết)
    expires_at = models.DateTimeField(db_index=True)
    # Hết hạn TUYỆT ĐỐI: family tạo lúc login + absolute_seconds (30 ngày).
    # KHÔNG reset khi xoay ⇒ phiên không thể kéo dài vô hạn (spec §37, §38).
    absolute_expires_at = models.DateTimeField(db_index=True)

    # ---- Metadata thiết bị (chỉ để hiển thị/điều tra, KHÔNG phải định danh
    # bảo mật — spec §74: client gửi device_name tùy ý, không được tin) ----
    user_agent = models.CharField(max_length=255, blank=True, default="")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_name = models.CharField(max_length=120, blank=True, default="")

    crt_at = models.DateTimeField(auto_now_add=True)
    upd_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "_0042_refresh_token_session"
        # Query nóng nhất là list session của 1 user + family revoke.
        indexes = [
            models.Index(fields=["user", "revoked_at"], name="idx_rt_user_revoked"),
            models.Index(fields=["family_id", "revoked_at"], name="idx_rt_family_revoked"),
        ]
        ordering = ["-last_used_at", "-crt_at"]
        verbose_name = "Refresh Token Session"
        verbose_name_plural = "Refresh Token Sessions"

    def __str__(self):
        state = "active" if self.revoked_at is None else "revoked"
        return f"{self.user_id} {state} {self.id}"

    @property
    def is_active(self) -> bool:
        """Còn dùng được không (chưa thu hồi + chưa hết cả 2 mốc hạn)."""
        from django.utils import timezone

        if self.revoked_at is not None:
            return False
        now = timezone.now()
        return self.expires_at > now and self.absolute_expires_at > now

    @property
    def was_rotated(self) -> bool:
        """Token này đã bị xoay hay chưa.

        `was_rotated` là điều kiện phân biệt "client gửi lại token cũ do chưa
        nhận được response" với "ai đó đang cố dùng lại token đã thu hồi".
        Token bị logout không có `replaced_by` ⇒ không tính là reuse (spec §16).
        """
        return self.replaced_by_id is not None

    @classmethod
    def active_for_user(cls, user) -> "models.QuerySet":
        """Các phiên còn hiệu lực của user (dùng cho list + logout-all)."""
        return cls.objects.filter(user=user, revoked_at__isnull=True)

    @classmethod
    def purge_expired(cls, keep_days: int = 30) -> int:
        """Xoá bản ghi hết hạn từ lâu.

        KHÔNG xoá ngay khi hết hạn: giữ ~30 ngày để còn đối chiếu được với
        audit log khi điều tra sự cố (spec §55).
        """
        from django.utils import timezone

        cutoff = timezone.now() - timedelta(days=max(int(keep_days), 0))
        deleted, _ = cls.objects.filter(absolute_expires_at__lt=cutoff).delete()
        return deleted
