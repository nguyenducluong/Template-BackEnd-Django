from django.conf import settings
from django.db import models

from apps.accounts.models import User
from apps.core.models import BaseModel

# The embedding column is a native pgvector ``vector(512)`` type on
# PostgreSQL (enabling ANN search via cosine distance).  On other
# backends (e.g. SQLite in development) it falls back to a JSON text
# column with a Python-side brute-force search.  The matching migration
# (0002) is conditional on the same setting so database state and
# migrations stay consistent on every backend.
if getattr(settings, "USE_PGVECTOR", False):
    from pgvector.django import VectorField
else:
    VectorField = None


class FaceEmbedding(BaseModel):
    """Model lưu face embeddings cho user."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="face_embeddings",
    )
    if VectorField is not None:
        embedding = VectorField(dimensions=512)
    else:
        embedding = models.TextField()  # JSON-encoded 512-dim vector
    image_path = models.CharField(max_length=500)  # Đường dẫn ảnh gốc
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "face_embeddings"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]