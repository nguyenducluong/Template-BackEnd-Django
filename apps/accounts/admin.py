from django.contrib import admin

from .models import JWTBlacklist, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("gen_id", "knox_id", "full_name", "status", "crt_at")
    list_filter = ("status",)
    search_fields = ("gen_id", "knox_id", "full_name")
    readonly_fields = ("crt_at", "upd_at", "change_pw_at", "password")
    ordering = ("-crt_at",)


@admin.register(JWTBlacklist)
class JWTBlacklistAdmin(admin.ModelAdmin):
    list_display = ("jti", "expires_at", "created_at")
    readonly_fields = ("jti", "expires_at", "created_at")
