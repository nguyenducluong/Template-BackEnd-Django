from django.urls import path

from . import views

urlpatterns = [
    path("auth/register", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/unlock", views.UnlockView.as_view(), name="auth-unlock"),
    path("auth/refresh", views.RefreshTokenView.as_view(), name="auth-refresh"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    # Đăng xuất MỌI thiết bị + quản lý phiên (spec §18/§19/§20).
    # `sessions/revoke` dùng POST chứ không DELETE — dự án cấm HTTP DELETE.
    path("auth/logout-all", views.LogoutAllView.as_view(), name="auth-logout-all"),
    path("auth/sessions", views.SessionListView.as_view(), name="auth-sessions"),
    path("auth/sessions/revoke", views.SessionRevokeView.as_view(), name="auth-sessions-revoke"),
    path("auth/me", views.MeView.as_view(), name="auth-me"),
    path("auth/change-password", views.ChangePasswordView.as_view(), name="auth-change-password"),
    path("auth/forgot-password", views.ForgotPasswordView.as_view(), name="auth-forgot-password"),
    path("auth/reset-password", views.ResetPasswordView.as_view(), name="auth-reset-password"),
    # ---- Port từ Laravel (OTP unlock — 2 bước) ----
    path("auth/required-otp-unlock", views.RequiredOtpUnlockView.as_view(), name="auth-required-otp-unlock"),
    path("auth/validate-otp-unlock", views.ValidateOtpUnlockView.as_view(), name="auth-validate-otp-unlock"),
]