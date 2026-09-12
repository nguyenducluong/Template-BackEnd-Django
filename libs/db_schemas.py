"""
Ensure PostgreSQL schemas exist (auto-provisioning).

Vấn đề: Django `migrate` KHÔNG TỰ tạo PostgreSQL SCHEMA — nó chỉ phát
`CREATE TABLE` và dựa vào `search_path` của connection. Nếu schema đầu tiên
trong search_path (VD "user") chưa tồn tại, bảng bị rơi nhầm vào schema
đầu tiên TỒN TẠI (thường là "public") hoặc lỗi "no schema has been selected".

Giải pháp: signal `connection_created` — MỖI LẦN một connection PostgreSQL
được mở (migrate, runserver, gunicorn, celery...), chạy
`CREATE SCHEMA IF NOT EXISTS` cho toàn bộ schema khai báo trong
settings.DB_SCHEMAS + settings.DB_DEFAULT_SCHEMA. Lệnh là idempotent nên
rẻ và an toàn khi chạy trên mọi connection.

Đăng ký qua AppConfig.ready() của apps.core (xem apps/core/apps.py).
Cần chạy thủ công? `python manage.py ensure_schemas`.
"""

import logging

from django.conf import settings

logger = logging.getLogger("apps")


def required_schemas() -> list[str]:
    """Danh sách schema cần tồn tại (dedupe, giữ thứ tự ổn định)."""
    schemas = list(dict.fromkeys(settings.DB_SCHEMAS.values()))
    default_schema = getattr(settings, "DB_DEFAULT_SCHEMA", "public")
    if default_schema and default_schema not in schemas:
        schemas.append(default_schema)
    return schemas


def ensure_schemas(connection) -> list[str]:
    """CREATE SCHEMA IF NOT EXISTS + pin django_migrations per schema.

    Trả về danh sách schema đã đảm bảo tồn tại. Bỏ qua với backend
    không phải PostgreSQL (SQLite dev...).

    Vì sao phải PIN bảng `django_migrations` vào TỪNG schema (schema-
    qualified) — không phụ thuộc search_path:
      - SchemaRouter thiết kế mỗi schema có tracker riêng (bảng
        django_migrations trong schema đó).
      - Nhưng CREATE TABLE không schema-qualified sẽ rơi vào schema ĐẦU TIÊN
        TỒN TẠI trong search_path → schema_info/face_id "nhìn thấy"
        user.django_migrations (đứng sau trong path) → tưởng đã migrate →
        KHÔNG tạo bảng, tracker dùng chung bị ghi chéo nhau.
      - CREATE TABLE schema-qualified (`"user".django_migrations`) ghim cứng
        bảng vào đúng schema → mỗi alias migrate dùng tracker riêng.
    """
    if connection.vendor != "postgresql":
        return []

    schemas = required_schemas()
    with connection.cursor() as cursor:
        for schema in schemas:
            # quote_name xử lý schema trùng keyword reserved (VD "user")
            quoted = connection.ops.quote_name(schema)
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted}")
            # Tracker migrate riêng cho schema (idempotent)
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {quoted}.django_migrations (
                    id bigserial NOT NULL PRIMARY KEY,
                    app varchar(255) NOT NULL,
                    name varchar(255) NOT NULL,
                    applied timestamp with time zone NOT NULL
                )
                """
            )
    logger.debug("Ensured PostgreSQL schemas %s on alias %s", schemas, connection.alias)
    return schemas


def ensure_schemas_on_connect(sender, connection, **kwargs) -> None:
    """Receiver cho signal `connection_created`."""
    try:
        ensure_schemas(connection)
    except Exception:  # pragma: no cover - never break the connection flow
        # Không chặn app khi DB user thiếu quyền CREATE SCHEMA — log rõ ra
        # để dev/deploy tự chạy `manage.py ensure_schemas` bằng tay.
        logger.warning(
            "Could not auto-create PostgreSQL schemas on alias %s "
            "(run `python manage.py ensure_schemas` manually)",
            getattr(connection, "alias", "?"),
            exc_info=True,
        )
