"""
Tạo (idempotent) các PostgreSQL schema khai báo trong settings.DB_SCHEMAS.

Dùng khi deploy / chẩn đoán — bình thường schemas được tự tạo bởi signal
`connection_created` (xem libs/db_schemas.py).

    python manage.py ensure_schemas
"""

from django.core.management.base import BaseCommand

from django.db import connections

from libs.db_schemas import ensure_schemas


class Command(BaseCommand):
    help = "CREATE SCHEMA IF NOT EXISTS cho mọi schema trong settings.DB_SCHEMAS"

    def handle(self, *args, **options):
        for alias in connections:
            connection = connections[alias]
            if connection.vendor != "postgresql":
                self.stdout.write(f"[{alias}] skip (backend={connection.vendor})")
                continue
            schemas = ensure_schemas(connection)
            self.stdout.write(self.style.SUCCESS(f"[{alias}] ensured: {', '.join(schemas)}"))
