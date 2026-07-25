"""
Database Router for PostgreSQL schema-based routing.

Maps individual models to specific PostgreSQL schemas using the DB_SCHEMAS
setting. Each schema gets its own database connection with the appropriate
search_path, so Django creates and queries tables in the correct schema.

Configuration in settings/base.py::

    DB_DEFAULT_SCHEMA = "system"  # schema for models not in DB_SCHEMAS
    DB_SCHEMAS = {
        "accounts.users": "auth",
        "face.faceembedding": "biometrics",
    }

Models not listed in DB_SCHEMAS use the "default" connection
(search_path=DB_DEFAULT_SCHEMA).
"""

from django.conf import settings


class SchemaRouter:
    """Route models to PostgreSQL schemas based on DB_SCHEMAS setting."""

    @property
    def schema_map(self) -> dict[str, str]:
        return getattr(settings, "DB_SCHEMAS", {})

    @property
    def default_schema(self) -> str:
        return getattr(settings, "DB_DEFAULT_SCHEMA", "public")

    def _get_db_alias(self, model) -> str | None:
        """Return the database alias for a model, or None for default."""
        key = f"{model._meta.app_label}.{model._meta.model_name}"
        schema = self.schema_map.get(key)
        if schema:
            if schema == self.default_schema:
                return "default"
            return f"schema_{schema}"
        return "default"

    def db_for_read(self, model, **hints) -> str | None:
        return self._get_db_alias(model)

    def db_for_write(self, model, **hints) -> str | None:
        return self._get_db_alias(model)

    def allow_relation(self, obj1, obj2, **hints) -> bool:
        """Allow relations between objects in any schema."""
        return True

    def allow_migrate(self, db: str, app_label: str, model_name: str | None = None, **hints) -> bool | None:
        """
        Ensure migrations run on the correct schema connection.

        - Models in DB_SCHEMAS migrate only on their schema connection.
        - Models not in DB_SCHEMAS migrate only on the "default" connection.
        - The django_migrations table is created on every connection that
          runs migrations (each schema needs its own tracking table).
        """
        # Always allow django_migrations table on any schema connection
        if app_label == "migrations" and model_name == "migration":
            if db == "default":
                return True
            if db.startswith("schema_"):
                return True
            return None

        if db == "default":
            # Only migrate models assigned to default_schema or not in DB_SCHEMAS
            if model_name:
                key = f"{app_label}.{model_name}"
                assigned = self.schema_map.get(key)
                # Migrate on default if: not in DB_SCHEMAS, or mapped to default_schema
                if assigned is None:
                    return True
                return assigned == self.default_schema
            return True

        # Schema-specific connection: only migrate models assigned to this schema
        if db.startswith("schema_"):
            schema_name = db.replace("schema_", "", 1)
            if model_name:
                key = f"{app_label}.{model_name}"
                assigned_schema = self.schema_map.get(key)
                return assigned_schema == schema_name
            return None

        return None
