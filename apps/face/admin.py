from django.contrib import admin

from .models import FaceEmbedding


@admin.register(FaceEmbedding)
class FaceEmbeddingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "is_active", "created_at")
    list_filter = ("is_active",)
    readonly_fields = ("embedding",)  # vector(512) — không edit qua form
