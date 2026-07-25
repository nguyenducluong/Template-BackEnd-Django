import json
import os
import time

import numpy as np
import cv2
from django.conf import settings
from django.db import connection
from insightface.app import FaceAnalysis

# pgvector is only available (and only makes sense) on PostgreSQL. When
# USE_PGVECTOR is disabled (e.g. SQLite in development) the matching falls
# back to a Python-side brute-force cosine similarity scan.
if getattr(settings, "USE_PGVECTOR", False):
    from pgvector.django import CosineDistance

    _USE_PGVECTOR = True
else:
    _USE_PGVECTOR = False


class FaceService:
    """Service xử lý face recognition với InsightFace."""

    def __init__(self):
        self.face_app = None

    def _get_face_app(self):
        if self.face_app is None:
            self.face_app = FaceAnalysis(
                name="buffalo_l",
                providers=["CPU"],
            )
            self.face_app.prepare(ctx_id=0, det_size=(640, 640))
        return self.face_app

    def _read_image(self, image_file):
        """Read an uploaded image file into an OpenCV BGR image.

        Resets the file pointer afterwards so the file can be read again
        (e.g. to save the original to disk).
        """
        data = image_file.read()
        try:
            image_file.seek(0)
        except (AttributeError, OSError):
            pass

        nparr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Invalid image file")
        return img

    def extract_embedding(self, image_file):
        """Trích xuất face embedding từ ảnh."""
        face_app = self._get_face_app()

        img = self._read_image(image_file)

        # Detect faces và lấy embedding
        faces = face_app.get(img)

        if not faces:
            raise ValueError("No face detected in image")

        if len(faces) > 1:
            raise ValueError("Multiple faces detected, please provide single face image")

        # Lấy embedding 512-dim
        embedding = faces[0].embedding
        return embedding.tolist()

    def save_face_image(self, user_id, image_file):
        """Lưu ảnh face vào disk và trả về path."""
        upload_dir = os.path.join(str(settings.MEDIA_ROOT), "faces")
        os.makedirs(upload_dir, exist_ok=True)

        filename = f"face_{user_id}_{int(time.time())}.jpg"
        filepath = os.path.join(upload_dir, filename)

        with open(filepath, "wb") as f:
            f.write(image_file.read())
        try:
            image_file.seek(0)
        except (AttributeError, OSError):
            pass

        return filepath

    def cosine_similarity(self, embedding1, embedding2):
        """Tính cosine similarity giữa 2 embeddings."""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

    def find_best_match(self, query_embedding, queryset=None):
        """Tìm embedding giống nhất với ``query_embedding``.

        On PostgreSQL this delegates to pgvector's cosine-distance operator
        (`<=>`) so similarity is computed entirely in the database (with an
        ANN index when one exists). On other backends it falls back to a
        Python-side brute-force scan over the JSON-stored embeddings.

        Returns ``(face_embedding_row, similarity)`` or ``(None, -1.0)`` if
        no active embedding exists.
        """
        from apps.face.models import FaceEmbedding

        qs = (queryset or FaceEmbedding.objects).filter(is_active=True)

        if _USE_PGVECTOR and connection.vendor == "postgresql":
            row = (
                qs.annotate(distance=CosineDistance("embedding"))
                .order_by("distance")
                .first()
            )
            if row is None:
                return None, -1.0
            return row, float(1.0 - row.distance)

        # Brute-force fallback (non-PostgreSQL backends).
        best, best_sim = None, -1.0
        for row in qs:
            stored = row.embedding
            if isinstance(stored, str):
                stored = json.loads(stored)
            sim = self.cosine_similarity(query_embedding, stored)
            if sim > best_sim:
                best, best_sim = row, sim
        return best, best_sim


face_service = FaceService()