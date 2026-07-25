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
    is_locked = models.BooleanField(default=False)

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

    # Account lockout helpers
    def is_account_locked(self) -> bool:
        """Return True if account is currently locked."""
        from django.utils import timezone
        if self.locked_until and self.locked_until > timezone.now():
            return True
        return False

    def record_failed_login(self) -> None:
        """Increment failed login attempts and lock if threshold exceeded."""
        from django.conf import settings
        from django.utils import timezone
        max_attempts = getattr(settings, "ACCOUNT_LOCKOUT_MAX_ATTEMPTS", 5)
        lockout_minutes = getattr(settings, "ACCOUNT_LOCKOUT_MINUTES", 15)
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = timezone.now() + timezone.timedelta(minutes=lockout_minutes)
        self.save(update_fields=["failed_login_attempts", "locked_until", "upd_at"])

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
