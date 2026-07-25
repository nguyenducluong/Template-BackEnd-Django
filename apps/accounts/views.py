from django.utils.translation import gettext as _
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from .models import User
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    TokenRefreshSerializer,
    UserSerializer,
)
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
    permission_classes = [permissions.AllowAny]
    throttle_classes = [RegisterRateThrottle]
    http_method_names = ["post", "options"]


@extend_schema(tags=["Authentication"])
class LoginView(APIView):
    """Custom JWT login — validates credentials and returns token pair."""

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
        return Response({
            "access": tokens["access"],
            "refresh": tokens["refresh"],
            "user": UserSerializer(user).data,
        })


@extend_schema(tags=["Authentication"])
class RefreshTokenView(APIView):
    """Refresh an access token using a valid refresh token (rotation enabled)."""

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
        access, refresh, _ = rotate_refresh_token(
            serializer.validated_data["refresh"]
        )
        return Response({
            "access": access,
            "refresh": refresh,
            "user": UserSerializer(user).data,
        })


@extend_schema(tags=["Authentication"])
class LogoutView(APIView):
    """Blacklist a refresh token to force logout."""

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
        return Response({"detail": _("Logout successful")})


@extend_schema(tags=["Authentication"])
class MeView(APIView):
    """Get or update current user profile."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "me"

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

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
        return Response(serializer.data)


@extend_schema(tags=["Authentication"])
class ChangePasswordView(APIView):
    """Change current user's password."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "user_write"
    http_method_names = ["post", "options"]

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={200: {
            "type": "object",
            "properties": {"detail": {"type": "string"}},
        }},
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"detail": _("Old password is incorrect")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": _("Password changed successfully")})

