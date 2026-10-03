"""Settings cho CHẠY TEST (`python manage.py test`).

VÌ SAO CẦN FILE NÀY
------------------
Dự án map mỗi model vào một PostgreSQL SCHEMA riêng (`DB_SCHEMAS` +
`SchemaRouter`), và mỗi schema có một connection riêng với `search_path`
khác nhau. Nhưng Django test runner chỉ tạo MỘT test database và chạy
`migrate` trên connection `default` — bảng thuộc schema khác sẽ không được
tạo, kết quả là:

    psycopg.errors.UndefinedTable: relation "_0010_user" does not exist

(Đây không phải lỗi của test nào cả — kể cả test có sẵn của dự án cũng vậy.)

CÁCH KHẮC PHỤC
--------------
Khi test, gộp TẤT CẢ model về schema `public` (schema mặc định, luôn tồn tại):
mọi bảng nằm cùng một schema, `search_path` giải quyết được, test runner tạo
đủ bảng. Hành vi logic của model KHÔNG đổi.

Cần chạy:  DJANGO_ENV=test python manage.py test <label>
"""

from .base import *  # noqa: F401,F403
from .development import *  # noqa: F401,F403

# Bỏ mapping schema: router không có entry nào match ⇒ mọi model rơi về
# connection `default` ⇒ tất cả bảng nằm trong schema `public`.
DB_SCHEMAS = {}
DB_DEFAULT_SCHEMA = "public"

# Xoá các connection `schema_*` sinh ra trong base.py: chúng trỏ tới schema
# không tồn tại trong test DB và chỉ gây nhiễu khi migrate.
for _alias in [name for name in DATABASES if name.startswith("schema_")]:  # noqa: F405
    del DATABASES[_alias]  # noqa: F405

# `search_path` chỉ còn public (nếu kế thừa list schema từ base.py).
DATABASES["default"]["OPTIONS"] = {  # noqa: F405
    **DATABASES["default"].get("OPTIONS", {}),  # noqa: F405
    "options": "-c search_path=public",
}

DATABASE_ROUTERS = ["libs.db_routers.SchemaRouter"]