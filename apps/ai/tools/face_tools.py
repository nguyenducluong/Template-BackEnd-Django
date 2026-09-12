"""
Tool tìm kiếm face (1:N) — tái dùng face_service. Nhận ảnh base64.
Chú ý: insightface load nặng — chỉ import trong handler (lazy).
Giới hạn kích thước ảnh để tránh DoS (S2) + bỏ gen_id khỏi response (giảm PII).
"""
from __future__ import annotations

import base64

from .base import ToolSpec

DEFAULT_THRESHOLD = 0.6
MAX_IMAGE_B64 = 6_000_000   # ~4.4MB raw ảnh
MAX_IMAGE_BYTES = 4_500_000


def _face_search(user, args: dict) -> dict:
    from apps.face.models import FaceEmbedding
    from apps.face.services.face_service import face_service

    image_b64 = args.get("image_base64", "")
    if not image_b64 or len(image_b64) > MAX_IMAGE_B64:
        return {"error": "image_base64 thiếu hoặc quá lớn (giới hạn 6MB base64)"}

    try:
        raw = base64.b64decode(image_b64, validate=False)
    except Exception:
        return {"error": "image_base64 không hợp lệ"}
    if len(raw) > MAX_IMAGE_BYTES:
        return {"error": "Ảnh quá lớn (giới hạn ~4.5MB)"}

    try:
        threshold = float(args.get("threshold", DEFAULT_THRESHOLD))
    except (TypeError, ValueError):
        threshold = DEFAULT_THRESHOLD
    threshold = max(0.0, min(1.0, threshold))

    import tempfile

    from django.core.files import File

    # lưu ra file tạm (xóa sau khi dùng) để insightface/opencv đọc được
    import os

    raw2 = raw
    del raw
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(raw2)
        tmp_path = tmp.name
    try:
        with open(tmp_path, "rb") as fh:
            from django.core.files import File as _File

            img_file = _File(fh, name="face.jpg")
            query = face_service.extract_embedding(img_file)
        best, sim = face_service.find_best_match(
            query_embedding=query,
            queryset=FaceEmbedding.objects.filter(is_active=True).select_related("user"),
        )
    except ValueError as exc:
        return {"error": str(exc)}
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass

    if best is not None and sim >= threshold:
        return {
            "match": {
                "user_id": best.user_id,
                "full_name": best.user.full_name,
                "similarity": sim,
            }
        }
    return {"match": None, "similarity": sim}


face_search_tool = ToolSpec(
    name="face.search",
    description="Tìm user gần giống nhất với ảnh (base64). Trả về user_id + similarity.",
    input_schema={
        "type": "object",
        "properties": {
            "image_base64": {"type": "string", "description": "Ảnh mã hóa base64 (JPG/PNG), tối đa ~4.5MB"},
            "threshold": {"type": "number", "minimum": 0, "maximum": 1, "description": "Ngưỡng tương đồng (mặc định 0.6)"},
        },
        "required": ["image_base64"],
        "additionalProperties": False,
    },
    handler=_face_search,
)