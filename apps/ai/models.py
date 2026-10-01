import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

# Cot vector cho RAG lich su chat.
# PostgreSQL + pgvector: native ``vector(N)`` (ho tro ANN index + <=> ).
# Backend khac: fallback ve TEXT chua JSON va quet bang Python (xem rag.py).
# So chieu lay tu settings.AI_EMBEDDING_DIMS de doi model embedding thi khop cot
# vector trong DB — hardcode se sinh migration sai.
if getattr(settings, "USE_PGVECTOR", False):
    from pgvector.django import VectorField
else:
    VectorField = None

EMBEDDING_DIMS = getattr(settings, "AI_EMBEDDING_DIMS", 1024)


class BaseModel(models.Model):
    """Abstract base model for AI app (mirrors apps.core.BaseModel pattern)."""

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


class FAQ(BaseModel):
    """Câu thường hỏi — lưu trong DB, trả về cho AI Assistant panel."""

    category = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=_("Phân loại FAQ (vd: Hệ thống, Tài khoản, Dữ liệu QC)"),
    )
    question = models.CharField(
        max_length=500,
        help_text=_("Câu hỏi"),
    )
    answer = models.TextField(
        help_text=_("Câu trả lời"),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_("Chỉ FAQ đang active mới hiển thị"),
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text=_("Thứ tự hiển thị (nhỏ hơn = trước)"),
    )

    class Meta:
        db_table = "ai_faq"
        ordering = ["sort_order", "-created_at"]
        verbose_name = _("FAQ")
        verbose_name_plural = _("FAQs")

    def __str__(self):
        return self.question[:80]


class AIChatSession(BaseModel):
    """Một phiên chat của user (mỗi phiên gồm nhiều message).

    Lưu VĨNH VIỄN — user chính user được xem lại bất cứ lúc nào.
    """

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="ai_chat_sessions",
    )
    title = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text=_("Tiêu đề phiên (lấy từ câu hỏi đầu tiên nếu không đặt)"),
    )
    is_active = models.BooleanField(default=True, db_index=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "ai_chat_sessions"
        ordering = ["-last_message_at", "-created_at"]
        verbose_name = _("AI Chat Session")
        verbose_name_plural = _("AI Chat Sessions")
        indexes = [
            models.Index(fields=["user", "-last_message_at"]),
        ]

    def __str__(self):
        return self.title or f"Phiên chat {self.id}"


class AIChatMessage(BaseModel):
    """Một lượt trong phiên chat + vector để RAG truy hồi.

    Tách `q_embedding` (vector CÂU HỎI) và `a_embedding` (vector CÂU TRẢ LỜI)
    vì hai bên nghĩa khác nhau: người dù hỏi bằng nghĩa câu hỏi, còn context
    đưa cho AI lại là nội dung đã trả lời. Gộp làm một sẽ truy sai.
    """

    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_CHOICES = [(ROLE_USER, _("User")), (ROLE_ASSISTANT, _("Assistant"))]

    session = models.ForeignKey(
        AIChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="ai_chat_messages",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_USER, db_index=True)
    content = models.TextField()

    if VectorField is not None:
        q_embedding = VectorField(dimensions=EMBEDDING_DIMS, null=True)
        a_embedding = VectorField(dimensions=EMBEDDING_DIMS, null=True)
    else:
        q_embedding = models.TextField(null=True, blank=True)  # JSON vector
        a_embedding = models.TextField(null=True, blank=True)  # JSON vector

    class Meta:
        db_table = "ai_chat_messages"
        ordering = ["created_at"]
        verbose_name = _("AI Chat Message")
        verbose_name_plural = _("AI Chat Messages")
        indexes = [
            models.Index(fields=["user", "session", "created_at"]),
        ]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
