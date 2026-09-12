"""
Unit tests cho auto-provisioning PostgreSQL schemas (không cần DB thật).

Run: python manage.py test tests.test_db_schemas -v 2
"""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from libs.db_schemas import ensure_schemas, required_schemas


def _fake_pg_connection(vendor="postgresql"):
    """Mock connection đủ dùng cho ensure_schemas()."""
    connection = mock.MagicMock()
    connection.vendor = vendor
    connection.alias = "schema_user"
    connection.ops.quote_name = lambda name: f'"{name}"'
    cursor = mock.MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    return connection, cursor


class RequiredSchemasTests(SimpleTestCase):
    @override_settings(
        DB_SCHEMAS={"accounts.user": "user", "info.organization": "info",
                    "info.shift": "info", "face.faceembedding": "face_id"},
        DB_DEFAULT_SCHEMA="public",
    )
    def test_dedup_and_order(self):
        self.assertEqual(required_schemas(), ["user", "info", "face_id", "public"])

    @override_settings(
        DB_SCHEMAS={"a.model": "s1"}, DB_DEFAULT_SCHEMA="s1",
    )
    def test_default_schema_deduped(self):
        self.assertEqual(required_schemas(), ["s1"])


class EnsureSchemasTests(SimpleTestCase):
    def test_skips_non_postgresql(self):
        connection, cursor = _fake_pg_connection(vendor="sqlite")
        self.assertEqual(ensure_schemas(connection), [])
        cursor.execute.assert_not_called()

    @override_settings(
        DB_SCHEMAS={"accounts.user": "user", "info.organization": "info"},
        DB_DEFAULT_SCHEMA="public",
    )
    def test_creates_schemas_and_pins_migration_tables(self):
        connection, cursor = _fake_pg_connection()
        ensured = ensure_schemas(connection)
        self.assertEqual(ensured, ["user", "info", "public"])
        executed = [
            " ".join(c.args[0].split()) for c in cursor.execute.call_args_list
        ]
        self.assertEqual(
            executed,
            [
                'CREATE SCHEMA IF NOT EXISTS "user"',
                'CREATE TABLE IF NOT EXISTS "user".django_migrations ( id bigserial NOT NULL PRIMARY KEY, app varchar(255) NOT NULL, name varchar(255) NOT NULL, applied timestamp with time zone NOT NULL )',
                'CREATE SCHEMA IF NOT EXISTS "info"',
                'CREATE TABLE IF NOT EXISTS "info".django_migrations ( id bigserial NOT NULL PRIMARY KEY, app varchar(255) NOT NULL, name varchar(255) NOT NULL, applied timestamp with time zone NOT NULL )',
                'CREATE SCHEMA IF NOT EXISTS "public"',
                'CREATE TABLE IF NOT EXISTS "public".django_migrations ( id bigserial NOT NULL PRIMARY KEY, app varchar(255) NOT NULL, name varchar(255) NOT NULL, applied timestamp with time zone NOT NULL )',
            ],
        )

    @override_settings(DB_SCHEMAS={"accounts.user": "user"}, DB_DEFAULT_SCHEMA="public")
    def test_error_is_swallowed_and_logged(self):
        connection, _ = _fake_pg_connection()
        connection.cursor.side_effect = RuntimeError("permission denied")
        # Không raise — chỉ log warning (không chặn flow mở connection).
        with self.assertLogs("apps", level="WARNING"):
            from libs.db_schemas import ensure_schemas_on_connect

            ensure_schemas_on_connect(None, connection)
