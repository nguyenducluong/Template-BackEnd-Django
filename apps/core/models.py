import uuid

from django.db import models


class BaseModel(models.Model):
    """
    Abstract base model for all models in the system.

    Features:
    - UUID primary key (secure, non-sequential, distributed-friendly)
    - created_at: auto-set on creation, indexed for fast ordering
    - updated_at: auto-updated on every save

    Note: Hard delete is used (no is_active/is_deleted fields).
    Data is deleted directly from the database.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        return str(self.id)