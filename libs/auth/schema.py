"""
drf-spectacular: khai báo scheme xác thực JWT (Bearer) cho OpenAPI.

Không có extension này, mọi endpoint sinh cảnh báo
``could not resolve authenticator <class 'libs.auth.authentication.JWTAuthentication'>``
và Swagger UI KHÔNG có nút Authorize ⇒ không gọi được API cần đăng nhập.

Module được import trong ``apps/api/apps.py::ApiConfig.ready()`` để drf-spectacular
đăng ký extension lúc khởi động.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """Ánh xạ ``libs.auth.authentication.JWTAuthentication`` → HTTP Bearer."""

    target_class = "libs.auth.authentication.JWTAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Dán access token (không kèm tiền tố 'Bearer ') vào ô Value.",
        }
