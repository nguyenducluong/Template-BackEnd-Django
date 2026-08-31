from rest_framework import serializers

from .models import GroupHeader, PagesHeader, SystemHeader


class GroupHeaderSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroupHeader
        fields = ["id", "group_vi", "group_en", "group_kr", "sort", "is_use"]


class PagesHeaderSerializer(serializers.ModelSerializer):
    class Meta:
        model = PagesHeader
        fields = ["id", "group_header", "page_vi", "page_en", "page_kr",
                   "sort", "is_use"]


class SystemHeaderSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemHeader
        fields = ["id", "page_header", "sort", "is_use", "is_mobile",
                   "view_vi", "view_en", "view_kr",
                   "header_vi", "header_en", "header_kr"]
