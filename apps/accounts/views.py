from django.utils.translation import gettext as _
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from django.utils import timezone

from drf_spectacular.utils import extend_schema

from .models import User
from services.redis_service import RedisService
from .serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    RequiredOtpUnlockSerializer,
    ResetPasswordSerializer,
    TokenRefreshSerializer,
    UnlockSerializer,
    UserSerializer,
    ValidateOtpUnlockSerializer,
    build_user_info,
)
from libs.responses import created_response, error_response, success_response
from libs.auth.jwt_utils import (
    blacklist_token,
    generate_tokens,
    rotate_refresh_token,
)
from libs.auth.throttling import (
    LoginRateThrottle,
    RegisterRateThrottle,
    ScopedRateThrottle,
)


@extend_schema(tags=["Authentication"])
class RegisterView(generics.CreateAPIView):
    """User registration endpoint."""

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]
    http_method_names = ["post", "options"]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return created_response(
            data=serializer.data,
            message=_("Registration successful. Please wait for approval."),
        )


@extend_schema(tags=["Authentication"])
class LoginView(APIView):
    """Custom JWT login — validates credentials and returns token pair."""
    # Credential nam trong body -> khong doc Bearer header (neu header chua
    # access token het han se bi 401 o tang authentication truoc khi vao view)
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]
    http_method_names = ["post", "options"]

    @extend_schema(
        request=LoginSerializer,
        responses={200: {
            "type": "object",
            "properties": {
                "access": {"type": "string"},
                "refresh": {"type": "string"},
                "user": {"type": "object"},
            },
        }},
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        tokens = generate_tokens(user)
        return success_response(
            data={
                "access": tokens["access"],
                "refresh": tokens["refresh"],
                "user": UserSerializer(user).data,
                # Port từ Laravel: user_info (ipv4, status_label, org_full_name...)
                # + auth_page điều hướng frontend (keyCheck=1 → bắt buộc đổi mật khẩu)
                "user_info": build_user_info(request, user),
                "auth_page": "change_password" if user.keyCheck == 1 else "user_info",
            },
            message=_("Login successful"),
        )


@extend_schema(tags=["Authentication"])
class UnlockView(APIView):
    """Unlock an account locked by failed login attempts (verify password)."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]
    http_method_names = ["post", "options"]

    @extend_schema(
        request=UnlockSerializer,
        responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}},
    )
    def post(self, request):
        serializer = UnlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        # Correct password proves identity -> clear lockout immediately
        user.reset_failed_login()
        return success_response(
            data={"detail": _("Account unlocked successfully. You can now log in.")},
            message=_("Account unlocked successfully"),
        )


@extend_schema(tags=["Authentication"])
class RefreshTokenView(APIView):
    """Refresh an access token using a valid refresh token (rotation enabled)."""

    # Refresh token trong body la credential — khong duoc de Bearer header
    # (co the chua access token het han) chan request o tang authentication
    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    http_method_names = ["post", "options"]

    @extend_schema(
        request=TokenRefreshSerializer,
        responses={200: {
            "type": "object",
            "properties": {
                "access": {"type": "string"},
                "refresh": {"type": "string"},
                "user": {"type": "object"},
            },
        }},
    )
    def post(self, request):
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        access, refresh, _new_jti = rotate_refresh_token(
            serializer.validated_data["refresh"]
        )
        return success_response(
            data={
                "access": access,
                "refresh": refresh,
                "user": UserSerializer(user).data,
                # Port từ Laravel: user_info + auth_page cho silent-refresh
                "user_info": build_user_info(request, user),
                "auth_page": "change_password" if user.keyCheck == 1 else "user_info",
            },
            message=_("Token refreshed"),
        )


@extend_schema(tags=["Authentication"])
class LogoutView(APIView):
    """Blacklist a refresh token to force logout."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    http_method_names = ["post", "options"]

    @extend_schema(
        request=LogoutSerializer,
        responses={200: {
            "type": "object",
            "properties": {"detail": {"type": "string"}},
        }},
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        blacklist_token(serializer.validated_data["refresh"])
        return success_response(data=None, message=_("Logout successful"))


@extend_schema(tags=["Authentication"])
class MeView(APIView):
    """Get or update current user profile."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "me"

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        serializer = UserSerializer(request.user)
        return success_response(data=serializer.data)

    @extend_schema(
        request=UserSerializer,
        responses={200: UserSerializer},
    )
    def post(self, request):
        serializer = UserSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(data=serializer.data, message=_("Profile updated"))


@extend_schema(tags=["Authentication"])
class ChangePasswordView(APIView):
    """Change current user's password (90-day policy + AD SSO keyCheck)."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "user_write"
    http_method_names = ["post", "options"]

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: {
            "type": "object",
            "properties": {
                "detail": {"type": "string"},
                "keyCheck": {"type": "integer"},
            },
        }},
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.change_pw_at = timezone.now()
        user.save(update_fields=["password", "change_pw_at"])

        return success_response(
            data={
                "detail": _("Password changed successfully"),
                "keyCheck": user.keyCheck,
                # Port từ Laravel: sau khi đổi mật khẩu → cấp user_info mới + vào hệ thống
                "user_info": build_user_info(request, user),
                "auth_page": "user_info",
            },
            message=_("Password changed successfully"),
        )


@extend_schema(tags=["Authentication"])
class ForgotPasswordView(APIView):
    """Generate and email an OTP for password reset (Redis-backed)."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    http_method_names = ["post", "options"]

    @extend_schema(
        request=ForgotPasswordSerializer,
        responses={200: {
            "type": "object",
            "properties": {
                "detail": {"type": "string"},
                "knox_id": {"type": "string"},
                "keyCheck": {"type": "integer"},
            },
        }},
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # ForgotPasswordSerializer exposes the resolved user via context
        # (validate_account stores it in self.context["user"]).
        user = serializer.context["user"]

        import secrets as _secrets
        otp = str(_secrets.randbelow(10 ** settings.OTP_LENGTH)).zfill(settings.OTP_LENGTH)
        otp_ttl = settings.OTP_EXPIRY_SECONDS

        # Use the same identifier resolution as ResetPasswordView (knox_id or gen_id)
        identifier = user.knox_id or user.gen_id
        RedisService.store_otp(identifier, otp, ttl=otp_ttl)

        subject = _("Password Reset OTP")
        message = _(
            "Your OTP for password reset is %(otp)s. "
            "It expires in %(minutes)d minutes."
        ) % {"otp": otp, "minutes": otp_ttl // 60}

        # Recipient: knox_id thay cho email (không có cột email trong
        # _0010_user); fallback về gen_id nếu user chưa có knox_id.
        recipient = f"{user.knox_id or user.gen_id}@example.com"

        from django.core.mail import send_mail
        from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=None,
                recipient_list=[recipient],
            )
        except Exception:
            # SMTP unavailable (e.g. local dev without a mail server):
            # fall back to console backend so the OTP is still deliverable
            # (printed to the Django dev-server console) and the flow works.
            import logging
            send_mail(
                subject=subject,
                message=message,
                from_email=None,
                recipient_list=[recipient],
                connection=ConsoleEmailBackend(),
            )
            logger = logging.getLogger("apps")
            # SECURITY: never log the OTP itself outside of local debugging —
            # anyone with access to logs could reset arbitrary passwords.
            if settings.DEBUG:
                logger.info(
                    "SMTP unavailable — forgot-password OTP for %s printed to console: %s",
                    identifier, otp,
                )
            else:
                logger.warning(
                    "SMTP unavailable — forgot-password OTP for %s NOT delivered.",
                    identifier,
                )

        return success_response(
            data={
                "detail": _("OTP sent. Please check your email."),
                "knox_id": user.knox_id,
                "keyCheck": user.keyCheck,
            },
            message=_("OTP sent. Please check your email."),
        )


@extend_schema(tags=["Authentication"])
class ResetPasswordView(APIView):
    """Verify OTP from Redis and reset password."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    http_method_names = ["post", "options"]

    @extend_schema(
        request=ResetPasswordSerializer,
        responses={200: {
            "type": "object",
            "properties": {"detail": {"type": "string"}},
        }},
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        otp = serializer.validated_data["otp"]

        identifier = user.knox_id or user.gen_id
        if not RedisService.verify_otp(identifier, otp):
            return error_response(
                message=_("Invalid or expired OTP"),
                errors={"otp": [_("Invalid or expired OTP")]},
            )

        user.set_password(serializer.validated_data["new_password"])
        user.change_pw_at = timezone.now()
        user.save(update_fields=["password", "change_pw_at"])

        RedisService.delete_otp(identifier)

        return success_response(
            data={"detail": _("Password reset successfully")},
            message=_("Password reset successfully"),
        )


# ---------------------------------------------------------------------------
# OTP unlock — port từ Laravel RequiredOtpUnlockService / ValidateOtpUnlockService
# (OTP 6 số, cache 180 giây; trả OTP trong response ở dev — TODO: gửi email)
# ---------------------------------------------------------------------------

OTP_UNLOCK_TTL = 180  # giây — khớp Laravel UserModel::CACHE_TIMEOUT


@extend_schema(tags=["Authentication"])
class RequiredOtpUnlockView(APIView):
    """Yêu cầu OTP mở khóa tài khoản (body: { knox_id })."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    http_method_names = ["post", "options"]

    @extend_schema(
        request=RequiredOtpUnlockSerializer,
        responses={
            200: {
                "type": "object",
                "properties": {"otp": {"type": "string"}, "time": {"type": "integer"}},
            },
            400: dict,
        },
    )
    def post(self, request):
        serializer = RequiredOtpUnlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Chỉ cho yêu cầu OTP khi tài khoản đang bị khóa (khớp Laravel: is_locked > 0)
        if not user.is_account_locked():
            return error_response(
                message=_("Account is not locked."),
                status=status.HTTP_400_BAD_REQUEST,
            )

        import secrets

        otp = str(secrets.randbelow(10 ** settings.OTP_LENGTH)).zfill(settings.OTP_LENGTH)
        RedisService.store_otp(f"unlock:{user.id}", otp, ttl=OTP_UNLOCK_TTL)
        # TODO: gửi OTP qua email (SMTP) — Laravel cũng đang TODO bước này

        return success_response(
            data={"otp": otp, "time": OTP_UNLOCK_TTL},
            message=_("OTP sent. Please check your email."),
        )


@extend_schema(tags=["Authentication"])
class ValidateOtpUnlockView(APIView):
    """Xác minh OTP mở khóa tài khoản (body: { knox_id, use_otp })."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"
    http_method_names = ["post", "options"]

    @extend_schema(
        request=ValidateOtpUnlockSerializer,
        responses={200: dict, 400: dict},
    )
    def post(self, request):
        serializer = ValidateOtpUnlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        # Tài khoản không bị khóa (khớp Laravel: auth_page sign_in + time 0)
        if not user.is_account_locked():
            return success_response(
                data={"auth_page": "sign_in", "time": 0},
                message=_("Account is not locked."),
            )

        identifier = f"unlock:{user.id}"
        # LƯU Ý: RedisService.get() nhận KEY ĐẦY ĐỦ (otp:<id>), khác
        # store_otp/delete_otp/verify_otp chỉ nhận identifier
        cached_otp = RedisService.get(f"otp:{identifier}")
        if cached_otp is None:
            # OTP hết hạn / chưa yêu cầu (khớp Laravel: otp_expired)
            return error_response(
                message=_("OTP has expired. Please request a new one."),
                errors={"otp": [_("OTP has expired. Please request a new one.")]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if cached_otp != serializer.validated_data["use_otp"]:
            return error_response(
                message=_("Invalid OTP."),
                errors={"otp": [_("Invalid OTP.")]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Đúng OTP → xóa OTP + reset lockout (khớp Laravel: is_locked = 0)
        RedisService.delete_otp(identifier)
        user.reset_failed_login()
        return success_response(
            data={
                "auth_page": "sign_in",
                "user_info": build_user_info(request, user),
            },
            message=_("Account unlocked successfully."),
        )

