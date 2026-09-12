from django.apps import AppConfig

from libs.db_schemas import ensure_schemas_on_connect
from django.db.backends.signals import connection_created
from django.dispatch import receiver


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self):
        # Tự tạo PostgreSQL schemas (user/info/face_id...) trước khi bất kỳ
        # connection nào chạy CREATE TABLE (migrate/runserver/celery...).
        connection_created.connect(ensure_schemas_on_connect, dispatch_uid="ensure_pg_schemas")
