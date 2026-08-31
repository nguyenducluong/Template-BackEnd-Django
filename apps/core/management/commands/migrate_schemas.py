"""
Management command to migrate all Postgres schemas (multi-schema routing).

Apps are split into separate schemas (user / face_id / info) and have cross-schema
foreign keys (accounts.User <-> info, face -> accounts). Order matters:
  1) Create all schemas.
  2) migrate accounts up to 0001 (user table WITHOUT org/shift FK).
  3) migrate info (all info tables + FK to user - already created).
  4) migrate accounts again (0002: add org/shift FK -> info).
  5) migrate face (FK to user - already created).

Usage:
    python manage.py migrate_schemas
"""
import psycopg2
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Migrate all apps in the correct order to resolve cross-schema FKs."

    def handle(self, *args, **options):
        self._ensure_schemas()
        self.stdout.write("== [1/4] accounts -> schema user (0001) ==")
        call_command("migrate", "accounts", "0001_initial", database="schema_user", interactive=False)
        self.stdout.write("== [2/4] info -> schema info ==")
        call_command("migrate", "info", database="schema_info", interactive=False)
        self.stdout.write("== [3/4] accounts finish (0002: org/shift FK) ==")
        call_command("migrate", "accounts", database="schema_user", interactive=False)
        self.stdout.write("== [4/4] face -> schema face_id ==")
        call_command("migrate", "face", database="schema_face_id", interactive=False)
        self.stdout.write(self.style.SUCCESS("\nAll schemas migrated (user / info / face_id)."))

    # ------------------------------------------------------------------
    def _ensure_schemas(self):
        """Create missing schemas via the default connection."""
        schemas = list(dict.fromkeys(settings.DB_SCHEMAS.values()))
        conf = settings.DATABASES["default"]
        conn = psycopg2.connect(
            dbname=conf["NAME"],
            user=conf.get("USER", "postgres"),
            password=conf.get("PASSWORD", ""),
            host=conf.get("HOST", "localhost"),
            port=conf.get("PORT", "5432"),
        )
        conn.autocommit = True
        cur = conn.cursor()
        for name in schemas:
            token = f'"{name}"' if name == "user" else name
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {token}")
            self.stdout.write(f"  schema {name}: OK")
        cur.close()
        conn.close()
