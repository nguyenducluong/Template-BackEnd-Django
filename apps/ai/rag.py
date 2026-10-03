"""
RAG cho lich su chat AI — truy hoi chinh message cua CHINH user.

VAI TRO:
  1. Luu vector cho moi message (de sau truy hoi).
  2. Khi user hoi cau moi, lay vai message cu lien quan lam boi canh cho AI.

NGUYEN TAC BAT BIET:
  - CHI truy hoi message cua chinh `user`. Loc o TANG QUERY
    (`AIChatMessage.objects.filter(user=...)`), khong dua vao check sau
    — nguoi dung khac khong the thay "coi qua" chi vi goi API dung.
  - RAG la TIN NANG PHU: Ollama chet / thieu model embedding / chua co du
    vector -> tra danh sach rong. TUYET DOI khong nem exception lam
    cau hoi chat that bai.
  - Tach `q_embedding` (vector cau hoi) va `a_embedding` (vector cau tra loi)
    vi hai ben nghia khac nhau: nguoi dung hoi bang nghia cau hoi, con boi
    canh dua cho AI la noi dung da tra loi.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

import numpy as np
from django.conf import settings
from django.db import connection

from libs.ai.embedding_client import embed_one

from .models import AIChatMessage, AIChatSession

logger = logging.getLogger("apps")

# Tu dong phong khi thu vien `jsonschema`/Ollama chua san: RAG khong duoc
# lam chap cau hoi chat.
_USE_PGVECTOR = bool(getattr(settings, "USE_PGVECTOR", False))

# So message toi da lay lam boi canh. Nho de tiet kiem token va doc.
DEFAULT_TOP_K = 4

# Nguong tuong dong duoi diem nay moi coi la "lien quan".
MIN_SIMILARITY = 0.35

# Nguong duoi day co the bo qua: khong tim thay gi lien quan thi thoi.
# Neu bo, boi canh se luon kem them rat nhieu noi dung lien quan nhat.
WEAK_SIMILARITY = 0.0

# Trần số message quét khi KHÔNG có pgvector (fallback Python). User chat nhiều
# sẽ có hàng chục nghìn dòng; quét hết mỗi lượt hỏi là nghẽn CPU + RAM.
MAX_SCAN_MESSAGES = 500


def _cosine(a, b) -> float:
    """Tu tinh cosine giua 2 vector (dung o nhanh fallback)."""
    v1 = np.array(a, dtype=float)
    v2 = np.array(b, dtype=float)
    n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
    if not n1 or not n2:
        return -1.0
    return float(np.dot(v1, v2) / (n1 * n2))


def _vector_field(message, field: str):
    """Lay vector tu message, chuan hoa ve list float (ho tro cot Text)."""
    value = getattr(message, field, None)
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    if not isinstance(value, (list, tuple)) or not value:
        return None
    return list(value)


def build_context(user, question: str, top_k: int = DEFAULT_TOP_K) -> List[Dict[str, str]]:
    """Tra ve `[{role, content}]` cua vai message lien quan nhat voi `question`.

    LUON tra danh sach (kem ca rong) — khong nem exception. RAG hop
    thi chat van chay binh thuong, chi thieu nguoi canh.
    """
    query_vector = None
    try:
        query_vector = embed_one(question or "")
    except Exception:  # noqa: BLE001 — RAG phu, khong duoc lam chap chat
        logger.exception("RAG: embed cau hoi that bai — bo qua RAG")
        return []

    if not query_vector:
        return []

    try:
        # CHI message cua chinh user nay.
        base = AIChatMessage.objects.filter(user=user).exclude(content="")
        if _USE_PGVECTOR and connection.vendor == "postgresql":
            try:
                from pgvector.django import CosineDistance
            except ImportError:
                CosineDistance = None
            if CosineDistance is not None:
                rows = []
                # PHẢI truyền CẢ vector query: `CosineDistance(field)` một tham số
                # là `CosineDistance(field, other_field)` — truyền thiếu sẽ raise
                # TypeError và rơi xuống fallback Python (chậm, quét toàn bảng).
                for field in ("q_embedding", "a_embedding"):
                    qs = base.exclude(**{f"{field}__isnull": True}).annotate(
                        distance=CosineDistance(field, query_vector)
                    )
                    for row in qs.order_by("distance")[:top_k]:
                        rows.append((row, 1.0 - float(row.distance)))
                rows.sort(key=lambda item: item[1], reverse=True)
                return _to_context(rows, top_k)
        # Fallback: quét bang Python tren vector luu JSON.
        # CHỈ xét `MAX_SCAN_MESSAGES` message gần nhất — user tích cực chat sẽ có
        # hàng chục nghìn dòng; quét hết mỗi lượt hỏi là nghẽn CPU. Ưu tiên tin
        # gần đây cũng hợp lý vì RAG chủ yếu phục vụ "nói nhớ lại vừa hỏi".
        scanned = base.order_by("-created_at").only("id", "role", "content", "q_embedding", "a_embedding")[:MAX_SCAN_MESSAGES]
        scored = []
        for message in scanned:
            best = -1.0
            for field in ("q_embedding", "a_embedding"):
                stored = _vector_field(message, field)
                if not stored:
                    continue
                if len(stored) != len(query_vector):
                    # Sai so chieu (doi model embedding) -> bo qua, KHONG
                    # so sanh se ra ket qua sai.
                    continue
                best = max(best, _cosine(query_vector, stored))
            if best >= MIN_SIMILARITY:
                scored.append((message, best))
        scored.sort(key=lambda item: item[1], reverse=True)
        return _to_context(scored, top_k)
    except Exception:  # noqa: BLE001
        logger.exception("RAG: truy hoi that bai — bo qua RAG")
        return []


def _to_context(scored, top_k: int) -> List[Dict[str, str]]:
    """Chuyen danh sach (message, score) thanh context cho AI."""
    context: List[Dict[str, str]] = []
    for message, score in scored[:top_k]:
        if score < WEAK_SIMILARITY:
            continue
        content = (message.content or "").strip()
        if not content:
            continue
        context.append({"role": message.role, "content": content[:2000]})
    return context


def save_message(user, session, role: str, content: str) -> Optional[AIChatMessage]:
    """Luu 1 message + vector hoa. Khong nem loi — that bai thi luu ban text.

    Vector hoa la viec TOI THUONG nen du co loi van giu message: mat vector
    chi nghia RAG ho so nhung lich su van dung cho nguoi doc lai.
    """
    content = (content or "").strip()
    if not content:
        return None
    vector = None
    try:
        vector = embed_one(content)
    except Exception:  # noqa: BLE001
        logger.warning("RAG: embed that bai — luu message khong co vector")

    # Cau hoi -> q_embedding, tra loi -> a_embedding.
    field = "q_embedding" if role == AIChatMessage.ROLE_USER else "a_embedding"
    return AIChatMessage.objects.create(
        session=session,
        user=user,
        role=role,
        content=content,
        **{field: vector} if vector else {},
    )


def touch_session(session) -> None:
    """Cap nhat `last_message_at` de danh sach phien sap xep dung."""
    from django.utils import timezone

    AIChatSession.objects.filter(id=session.id).update(last_message_at=timezone.now())
