from django.contrib import admin

from .models import (
    GroupHeader,
    HeaderOrganization,
    HeaderOrganizationUserRegistration,
    HeaderRegistration,
    Organization,
    PagesHeader,
    Shift,
    SystemHeader,
    SystemPermission,
    SystemPower,
    UserHeaderRegistration,
    UserSystemPermissionRegistration,
    Vendor,
    Material,
)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "level", "parent", "sort", "is_use")
    list_filter = ("level", "is_use")
    search_fields = ("name",)


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("id", "shift_vi", "shift_en", "shift_kr")


@admin.register(GroupHeader)
class GroupHeaderAdmin(admin.ModelAdmin):
    list_display = ("id", "group_vi", "group_en", "sort", "is_use")
    list_filter = ("is_use",)


@admin.register(PagesHeader)
class PagesHeaderAdmin(admin.ModelAdmin):
    list_display = ("id", "page_vi", "group_header", "sort", "is_use")
    list_filter = ("is_use",)


@admin.register(SystemHeader)
class SystemHeaderAdmin(admin.ModelAdmin):
    list_display = ("id", "header_vi", "page_header", "sort", "is_use", "is_mobile")
    list_filter = ("is_use", "is_mobile")
    search_fields = ("header_vi", "header_en", "view_vi")


admin.site.register(Vendor)
admin.site.register(Material)
admin.site.register(SystemPower)
admin.site.register(HeaderRegistration)
admin.site.register(UserHeaderRegistration)
admin.site.register(HeaderOrganization)
admin.site.register(HeaderOrganizationUserRegistration)
admin.site.register(SystemPermission)
admin.site.register(UserSystemPermissionRegistration)
