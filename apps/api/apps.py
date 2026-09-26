from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.api"
    label = "api"

    def ready(self):
        # Đăng ký scheme Bearer cho Swagger/OpenAPI (libs/auth/schema.py).
        import libs.auth.schema  # noqa: F401