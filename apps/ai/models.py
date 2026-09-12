import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


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