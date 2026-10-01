"""
Ollama EMBEDDING client (vector hoa text) - dung cho RAG lich su chat.

Tach rieng khoi ``ollama_client.py`` vi:
  - endpoint khac nhau (``/api/embed`` thay vi ``/api/chat``)
  - model khac nhau (bge-m3 de tim kiem da ngon ngu, KHONG phai model chat)
  - KHONG stream (chi tra vector xong moi luu duoc)

Vi sao bge-m3: ho tro da ngon ngu (co ca tieng Viet) - dung RAG cho app co
3 ngon ngu (vi/en/kr). ``nomic-embed-text`` nhe hon nhung chi tieng Anh.
"""

import logging
from typing import List, Optional

import requests

from django.conf import settings

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "bge-m3"
DEFAULT_DIMS = 1024
# Embedding nhanh hon chat nhieu: timeout nho hon, tranh treo request RAG.
DEFAULT_TIMEOUT = 30

logger = logging.getLogger("apps")


class EmbeddingClient:
    """Sinh vector cho text qua Ollama ``/api/embed``.

    Usage::

        client = EmbeddingClient()
        vectors = client.embed(["xin chao", "hello"])
    """

    def __init__(self, base_url=None, model=None, timeout=None, dims=None):
        self.base_url = str(base_url or getattr(settings, "OLLAMA_BASE_URL", DEFAULT_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or getattr(settings, "AI_EMBEDDING_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL
        self.timeout = int(timeout or getattr(settings, "AI_EMBEDDING_TIMEOUT", DEFAULT_TIMEOUT) or DEFAULT_TIMEOUT)
        # SO CHIEU vector. Phai khop that su cua model, vi sai so luong lam pgvector
        # tu cho loi khi INSERT, va lam do do cosine sai.
        self.dims = int(dims or getattr(settings, "AI_EMBEDDING_DIMS", DEFAULT_DIMS) or DEFAULT_DIMS)

    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        """Model embedding da duoc ``ollama pull`` chua? (KHONG generate de nhanh)"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
        except requests.exceptions.RequestException:
            return False
        if not response.ok:
            return False
        try:
            models = response.json().get("models") or []
        except ValueError:
            return False
        base = self.model.split(":")[0]
        return any(str(m.get("name", "")).split(":")[0] == base for m in models)

    def embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Embed 1 nhieu text.

        Tra ``None`` (khong nem exception) khi that bai. Ly do: RAG la TIN NANG
        PHU - Ollama chet / model chua pull thi chat van chay binh thuong, chi mat
        phan "nho ve cua toi truoc do". Nem exception se lam user mat ca cuoc chat.
        """
        clean = [str(t).strip() for t in (texts or []) if str(t or "").strip()]
        if not clean:
            return []
        try:
            response = requests.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": clean}, timeout=self.timeout)
        except requests.exceptions.Timeout:
            logger.warning("Embedding timed out after %ss", self.timeout)
            return None
        except requests.exceptions.RequestException:
            logger.warning("Cannot reach Ollama at %s for embedding", self.base_url)
            return None

        if not response.ok:
            logger.warning("Embedding failed (%s): %s", response.status_code, response.text[:200])
            return None
        try:
            payload = response.json()
        except ValueError:
            logger.warning("Embedding response khong phai JSON")
            return None

        vectors = payload.get("embeddings") or []
        if not vectors:
            # Ollama ban cu tra "embedding" (1 vector) thay vi "embeddings".
            single = payload.get("embedding")
            vectors = [single] if single else []
        if not vectors:
            return None

        # Canh so luong theo input de khong lech index khi server bo text rong.
        vectors = list(vectors)[: len(clean)]
        if len(vectors) != len(clean):
            logger.warning("Embedding count mismatch: got %s, expected %s", len(vectors), len(clean))
            return None
        if len(vectors[0]) != self.dims:
            # KHONG tu chua vector sai so luong: bao loi de admin doi model/setting.
            logger.warning("Embedding dims mismatch: model %s tra %s chieu, setting AI_EMBEDDING_DIMS=%s", self.model, len(vectors[0]), self.dims)
            return None
        return vectors

    def embed_one(self, text: str) -> Optional[List[float]]:
        """Embed 1 text - tra vector hoac None."""
        vectors = self.embed([text])
        if not vectors:
            return None
        return vectors[0]


# Client LAZY (khong khoi tao luc import).
# Ly do: module nay duoc import boi libs/ai/__init__.py, co the truoc khi Django
# configure xong settings -> getattr(settings, ...) tra ve LazySettings chua co
# value, va `.rstrip()` se AttributeError, lam vong import ca libs.ai.
_client = None


def get_client() -> EmbeddingClient:
    """Tra client embedding, tao lazy 1 lan roi giu lai cho cac request sau."""
    global _client
    if _client is None:
        _client = EmbeddingClient()
    return _client


# Ham tien ich dung truc tiep cho apps/ai/services/rag.py - deu di qua client lazy.
def embed_texts(texts):
    return get_client().embed(texts)


def embed_one(text):
    return get_client().embed_one(text)


def embedding_is_available() -> bool:
    return get_client().is_available()
