from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import User


class LoginSerializer(serializers.Serializer):
    """Validate gen_id/knox_id + password and return JWT tokens."""

    account = serializers.CharField(label="gen_id or knox_id")
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from django.db.models import Q
        from django.utils import timezone

        account = attrs["account"]

        # Phase 1c: Single query using Q objects instead of 2 separate queries
        try:
            user = User.objects.select_related("org", "shift").get(
                Q(gen_id=account) | Q(knox_id=account)
            )
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            user = None

        if not user or not user.is_active:
            raise serializers.ValidationError(
                _("Invalid credentials or account inactive")
            )

        # Phase 1d: Check account lockout
        if user.is_account_locked():
            remaining = (user.locked_until - timezone.now()).seconds // 60 + 1
            raise serializers.ValidationError(
                _("Account locked due to too many failed attempts. "
                  "Try again in %(minutes)d minutes.") % {"minutes": remaining}
            )

        if not user.check_password(attrs["password"]):
            # Phase 1d: Record failed login attempt
            user.record_failed_login()
            raise serializers.ValidationError(_("Invalid credentials"))

        # Phase 1d: Reset failed login on success
        user.reset_failed_login()
        attrs["user"] = user
        return attrs


class UnlockSerializer(serializers.Serializer):
    """Unlock an account locked by failed login attempts.

    User proves identity by re-entering the correct password; on success
    the failed-attempt counter and lockout are cleared immediately
    (no need to wait for ACCOUNT_LOCKOUT_MINUTES to elapse).
    """

    account = serializers.CharField(label="gen_id or knox_id")
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from django.db.models import Q

        account = attrs["account"]
        try:
            user = User.objects.get(Q(gen_id=account) | Q(knox_id=account))
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            user = None

        if not user or not user.is_active:
            raise serializers.ValidationError(
                _("Invalid credentials or account inactive")
            )

        if not user.check_password(attrs["password"]):
            raise serializers.ValidationError(_("Invalid credentials"))

        attrs["user"] = user
        return attrs


def read_refresh_token(request) -> str:
    """Lấy refresh token từ request, ưu tiên header `Authorization: Bearer`.

    VÌ SAO ƯU TIÊN HEADER:
    - `libs/auth/refresh_tokens.py` sinh token OPAQUE có tiền tố `rt_`. Header
      Bearer là chỗ quy ước cho credential, tránh nhầm với access token.
    - Endpoint này có `authentication_classes = []` nên Bearer KHÔNG bị chặn ở
      tầng DRF.

    Vẫn fallback về body cho client CŨ (đang gửi `{refresh: ...}`) — đường này
    chỉ để deploy không làm hỏng ai, không phải đường chính.

    @param request DRF request
    @returns str chuỗi rỗng nếu không có token ở đâu cả
    """
    header = (request.META.get("HTTP_AUTHORIZATION") or "").strip()
    if header:
        parts = header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
    # Multipart / form: `params` có thể là JSON string (xem systems dispatcher).
    data = request.data if isinstance(request.data, dict) else {}
    return str(data.get("refresh") or "").strip()


class TokenRefreshSerializer(serializers.Serializer):
    """Refresh access token bằng refresh token (có rotation).

    Refresh token được đọc từ `Authorization: Bearer` (fallback body) — xem
    `read_refresh_token`.

    Không gọi `rotate_refresh_token` (JWT cũ) nữa: luồng mới dùng
    `libs/auth.refresh_tokens.rotate()` với Token Family + Reuse Detection.
    Lỗi nghiệp vụ được ném ra kèm `code` máy đọc được để FE quyết định retry
    hay buộc đăng nhập lại.
    """

    def validate(self, attrs):
        from libs.auth import refresh_tokens as rt
        from libs.exceptions import AuthRefreshError

        request = self.context.get("request")
        raw_token = read_refresh_token(request) if request is not None else ""

        # Token OPAQUE (tiền tố `rt_`) là luồng chính. Token KHÔNG có tiền tố là
        # JWT cũ đã cấp trước khi lên Token Family → chuyển tiếp 1 lần sang
        # opaque để KHÔNG đăng xuất oàn mọi phiên đang chạy lúc deploy.
        legacy = not str(raw_token).startswith(rt.TOKEN_PREFIX)
        try:
            result = rt.rotate_legacy_jwt(raw_token, request=request) if legacy else rt.rotate(raw_token, request=request)
        except rt.RefreshTokenError as exc:
            # `AuthRefreshError` (401) chứ KHÔNG phải ValidationError (400):
            # spec §23 xếp hết lỗi refresh token vào 401.
            raise AuthRefreshError({"code": exc.code, "detail": str(exc) or exc.code})

        attrs["user"] = result["session"].user
        attrs["access"] = result["access_token"]
        attrs["refresh"] = result["refresh_token"]
        attrs["session"] = result["session"]
        return attrs


class LogoutSerializer(serializers.Serializer):
    """Nhận refresh token (Bearer hoặc body) để thu hồi phiên.

    Không bắt buộc: logout phải idempotent — client gọi được kể cả khi token
    đã chết (spec §17).
    """

    refresh = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context.get("request")
        attrs["raw_token"] = read_refresh_token(request) if request is not None else ""
        return attrs


class UserSerializer(serializers.ModelSerializer):
    """User serializer with joined Organization (hierarchy) and Shift data."""

    # ---- Organization join (like view_0010_user) ----
    # Phase 2b: Use cached fields to avoid N+1 query
    org_id = serializers.IntegerField(source="org.id", read_only=True)
    org_name = serializers.CharField(source="org.name", read_only=True)
    org_level = serializers.IntegerField(source="org.level", read_only=True)
    org_full_path = serializers.CharField(source="org.cached_full_path", read_only=True)
    org_full_name = serializers.CharField(source="org.cached_full_name", read_only=True)

    # ---- Shift join ----
    shift_id = serializers.IntegerField(source="shift.id", read_only=True)
    shift_vi = serializers.CharField(source="shift.shift_vi", read_only=True)
    shift_en = serializers.CharField(source="shift.shift_en", read_only=True)
    shift_kr = serializers.CharField(source="shift.shift_kr", read_only=True)

    # ---- Password policy fields ----
    change_pw_at = serializers.DateTimeField(read_only=True)
    keyCheck = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "gen_id", "knox_id", "full_name", "status",
            "crt_at", "upd_at", "change_pw_at", "keyCheck",
            # organization join
            "org_id", "org_name", "org_level", "org_full_path", "org_full_name",
            # shift join
            "shift_id", "shift_vi", "shift_en", "shift_kr",
        ]
        read_only_fields = [
            # Only full_name is writable (profile update via /auth/me POST);
            # joined org/shift fields are read-only — change via admin/user API
            "id", "gen_id", "knox_id", "status",
            "crt_at", "upd_at", "change_pw_at", "keyCheck",
            "org_id", "org_name", "org_level", "org_full_path", "org_full_name",
            "shift_id", "shift_vi", "shift_en", "shift_kr",
        ]


class RegisterSerializer(serializers.ModelSerializer):
    """Registration serializer with password validation."""

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "gen_id", "knox_id", "full_name", "org", "shift",
                  "password", "password_confirm"]
        read_only_fields = ["id"]

    def validate_password(self, value):
        """Phase 1e: Validate password complexity."""
        from libs.auth.password_validation import StrongPasswordValidator
        validator = StrongPasswordValidator()
        validator.validate(value)
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(_("Passwords do not match"))
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user



class ChangePasswordSerializer(serializers.Serializer):
    """Change password serializer with 90-day policy and AD SSO check."""

    old_password = serializers.CharField(required=False)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_new_password(self, value):
        """Validate password complexity."""
        from libs.auth.password_validation import StrongPasswordValidator
        validator = StrongPasswordValidator()
        validator.validate(value)
        return value

    def validate(self, attrs):
        user = self.context["request"].user

        # If password is expired (>90 days), old_password is not required
        if not user.is_password_expired():
            if not attrs.get("old_password"):
                raise serializers.ValidationError(
                    _("Old password is required.")
                )
            if not user.check_password(attrs["old_password"]):
                raise serializers.ValidationError(
                    _("Old password is incorrect.")
                )

        attrs["user"] = user
        return attrs


class RevokeSessionSerializer(serializers.Serializer):
    """Body cho `POST /accounts/auth/sessions/revoke`.

    VÌ SAO POST mà không DELETE: dự án CẤM HTTP DELETE ở cả 3 tầng
    (`libs/http_policy.py`, Nginx `limit_except`, ESLint). Xem `.clinerules`.
    """

    session_id = serializers.UUIDField()


class ForgotPasswordSerializer(serializers.Serializer):
    """Validate account identifier and trigger OTP generation."""

    account = serializers.CharField(
        help_text="gen_id or knox_id of the user requesting password reset"
    )

    def validate_account(self, value):
        from django.db.models import Q
        try:
            user = User.objects.get(
                Q(gen_id=value) | Q(knox_id=value)
            )
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            raise serializers.ValidationError(
                _("No account found with this identifier.")
            )
        if not user.is_active:
            raise serializers.ValidationError(
                _("Account is inactive.")
            )
        self.context["user"] = user
        return value


class ResetPasswordSerializer(serializers.Serializer):
    """Verify OTP and set a new password."""

    account = serializers.CharField()
    otp = serializers.CharField(min_length=4, max_length=10)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_new_password(self, value):
        from libs.auth.password_validation import StrongPasswordValidator
        validator = StrongPasswordValidator()
        validator.validate(value)
        return value

    def validate(self, attrs):
        from django.db.models import Q
        try:
            user = User.objects.get(
                Q(gen_id=attrs["account"]) | Q(knox_id=attrs["account"])
            )
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            raise serializers.ValidationError(
                _("No account found with this identifier.")
            )
        attrs["user"] = user
        return attrs


# ---------------------------------------------------------------------------
# Helpers port từ Laravel (shape `user_info` khớp UserModel::getUserInfo)
# ---------------------------------------------------------------------------

# Nhãn trạng thái theo ngôn ngữ — port từ Laravel UserModel::STATUS_USER
# (dùng dict thay gettext để hành vi khớp 1-1 với Laravel, không phụ thuộc .mo)
STATUS_LABELS = {
    0: {"vi": "Chờ phê duyệt", "en": "Waiting for approval", "kr": "승인 대기 중"},
    1: {"vi": "Đã phê duyệt", "en": "Approved", "kr": "승인됨"},
    2: {"vi": "Bị từ chối", "en": "Rejected", "kr": "거부됨"},
    3: {"vi": "Bị khóa", "en": "Blocked", "kr": "차단됨"},
    4: {"vi": "Đã xóa", "en": "Deleted", "kr": "삭제됨"},
}


def get_client_ip(request) -> str:
    """IP client (tôn trọng X-Forwarded-For khi có proxy)."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def build_user_info(request, user) -> dict:
    """Dựng object `user_info` trả về frontend — shape khớp Laravel.

    `org_full_name` phải lấy `org.cached_full_name` (đường dẫn đầy đủ
    "IQC 2P => IQC G => SET QC Team => Incoming MEC") để KHỚP với
    `UserSerializer.org_full_name` và với `Organization.full_name`. Trước đây
    chỗ này lấy `org.name` ⇒ cùng một key mà hai nơi trả hai giá trị khác nhau
    (header hiển thị "Incoming MEC" còn bảng chi tiết hiển thị cả đường dẫn).
    """
    language = getattr(request, "LANGUAGE_CODE", None) or "vi"
    labels = STATUS_LABELS.get(user.status) or {}
    org_full_name = ""
    if user.org_id:
        org_full_name = user.org.cached_full_name or user.org.name or ""
    return {
        # BẮT BUỘC có `id`: đây là khoá chính của DB, dùng để so sánh với
    # `Message.sender_id` / `ConversationMember.user_id` phía chat. Thiếu nó thì
        # `state.auth.user_info.id` là `undefined` ⇒ FE không xác định được tin
        # nào là của chính mình ⇒ MỌI tin hiển thị bên trái.
        "id": user.id,
        "gen_id": user.gen_id,
        "knox_id": user.knox_id,
        "full_name": user.full_name,
        "status": user.status,
        "org_id": user.org_id,
        "org_full_name": org_full_name,
        "shift_id": user.shift_id,
        "change_pw_at": (
            user.change_pw_at.strftime("%Y-%m-%d %H:%M:%S")
            if user.change_pw_at
            else None
        ),
        "ipv4": get_client_ip(request),
        "status_label": labels.get(language) or labels.get("vi") or "",
    }


class RequiredOtpUnlockSerializer(serializers.Serializer):
    """Yêu cầu OTP mở khóa tài khoản (body: { knox_id })."""

    knox_id = serializers.CharField()

    def validate(self, attrs):
        try:
            user = User.objects.get(knox_id=attrs["knox_id"])
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            raise serializers.ValidationError(
                _("No account found with this Knox ID.")
            )
        attrs["user"] = user
        return attrs


class ValidateOtpUnlockSerializer(serializers.Serializer):
    """Xác minh OTP mở khóa (body: { knox_id, use_otp })."""

    knox_id = serializers.CharField()
    use_otp = serializers.CharField(min_length=4, max_length=10)

    def validate(self, attrs):
        try:
            user = User.objects.get(knox_id=attrs["knox_id"])
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            raise serializers.ValidationError(
                _("No account found with this Knox ID.")
            )
        attrs["user"] = user
        return attrs

