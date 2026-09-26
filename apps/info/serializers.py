import json

from django.utils.translation import gettext as _

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


class JsonOrStringField(serializers.JSONField):
    """JSONField nhận CẢ object JSON LẪN chuỗi JSON.

    DRF ``JSONField`` chỉ tự ``json.loads`` khi field được đánh dấu là HTML input
    (``binary=True`` hoặc marker ``is_json_string`` sinh từ ``request.POST``).
    Với multipart do FE gửi (``build_form_data`` trong STD/src/axios/axios.jsx),
    giá trị object được stringify thành chuỗi → cần parse tường minh ở đây.

    Chuỗi rỗng/None ⇒ ``None`` (field không gửi).
    """

    def to_internal_value(self, data):
        if isinstance(data, str):
            raw = data.strip()
            if not raw:
                return None
            try:
                data = json.loads(raw)
            except ValueError:
                raise serializers.ValidationError(_("Value must be valid JSON."))
        return super().to_internal_value(data)


# ---------------------------------------------------------------------------
# Dispatcher `POST /api/v1/info/dispatch` — xem apps/info/dispatch.py
# ---------------------------------------------------------------------------
class InfoDispatchSerializer(serializers.Serializer):
    """Payload của dispatcher info — 1 endpoint cho MỌI thao tác của app info.

    Method: CHỈ POST (không PUT/PATCH/DELETE — xem libs/http_policy.py).

        {
            "resource": "group_headers" | "page_headers" | "system_headers" | "headers",
            "action":   "list" | "retrieve" | "structure"
                        | "create" | "update" | "delete" | "reorder",
            "id":       12,
            "data":     {...},   # create/update/delete-reorder
            "params":   {...}    # list/retrieve/structure
        }

    ``data``/``params`` nhận cả object JSON lẫn chuỗi JSON (multipart do FE gửi
    kèm file) — DRF JSONField tự parse chuỗi.
    """

    RESOURCE_CHOICES = ("group_headers", "page_headers", "system_headers", "headers")
    ACTION_CHOICES = ("list", "retrieve", "structure", "create", "update", "delete", "reorder")

    resource = serializers.ChoiceField(choices=RESOURCE_CHOICES)
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    id = serializers.IntegerField(required=False, allow_null=True)
    # required=False + JsonOrStringField: multipart (FE gửi kèm file) truyền
    # `data`/`params` dạng chuỗi JSON nên phải parse tường minh.
    data = JsonOrStringField(required=False, allow_null=True)
    params = JsonOrStringField(required=False, allow_null=True)

    def validate_data(self, value):
        if value is not None and not isinstance(value, (dict, list)):
            raise serializers.ValidationError(_("Field 'data' must be an object or array."))
        return value

    def validate_params(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError(_("Field 'params' must be an object."))
        return value

    def validate(self, attrs):
        action = attrs.get("action")
        if action in ("retrieve", "update", "delete") and not attrs.get("id"):
            raise serializers.ValidationError({"id": _("Field 'id' is required for this action.")})
        if action in ("create", "reorder") and not attrs.get("data"):
            raise serializers.ValidationError({"data": _("Field 'data' is required for this action.")})
        return attrs
