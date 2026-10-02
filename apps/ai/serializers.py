from django.utils.translation import gettext as _
from rest_framework import serializers

from .models import AIChatMessage, AIChatSession, FAQ


class AIChatMessageSerializer(serializers.Serializer):
    """One message in the conversation history sent to the AI."""

    role = serializers.ChoiceField(choices=["user", "assistant", "system"])
    # `max_length` chặn 1 tin khổng lồ làm phình context (và vượt context window
    # của model nhỏ như qwen2.5-coder:1.5b). 4000 ký tự là trần hợp lý cho 1 lượt.
    content = serializers.CharField(allow_blank=False, trim_whitespace=True, max_length=4000)


class AIChatRequestSerializer(serializers.Serializer):
    """Payload for POST /api/v1/ai/chat/."""

    messages = AIChatMessageSerializer(many=True, min_length=1, max_length=50)

    # Phiên chat đang mở. Lần đầu FE gửi rỗng, BE tự tạo và trả về id;
    # các lượt sau gửi lại id để gom vào CÙNG một phiên (lịch sử bền vững).
    session_id = serializers.UUIDField(required=False, allow_null=True)

    # Kích hoạt tool-calling (agent đọc/phân tích dữ liệu hệ thống). Mặc định BẬT.
    tools = serializers.BooleanField(default=True)
    max_turns = serializers.IntegerField(min_value=1, max_value=6, default=3)

    def validate_messages(self, value):
        # The last message must come from the user (that is the question).
        if value[-1]["role"] != "user":
            raise serializers.ValidationError(
                _("The last message must have role 'user'.")
            )
        return value


class FAQSerializer(serializers.ModelSerializer):
    """Serializer cho FAQ — trả về danh sách câu thường hỏi."""

    class Meta:
        model = FAQ
        fields = ["id", "category", "question", "answer", "sort_order"]

class AIChatSessionSerializer(serializers.ModelSerializer):
    """Danh sách phiên chat (dùng cho popover lịch sử ở FE).

    `message_count` để FE hiển thị "(n tin)" mà không phải gọi thêm request.
    """

    message_count = serializers.SerializerMethodField()

    class Meta:
        model = AIChatSession
        fields = ["id", "title", "is_active", "last_message_at", "created_at", "message_count"]

    def get_message_count(self, obj) -> int:
        # annotate() đã tính sẵn thì dùng luôn, tránh N+1 query cho mỗi phiên.
        return int(getattr(obj, "message_count", 0) or 0)


class AIChatMessageRowSerializer(serializers.ModelSerializer):
    """Một lượt chat trả về cho FE (nhãn `...Row` để không trùng

    `AIChatMessageSerializer` ở trên — cái đó là serializer cho REQUEST.
    """

    class Meta:
        model = AIChatMessage
        fields = ["id", "session_id", "role", "content", "created_at"]


class AIChatSessionCreateSerializer(serializers.Serializer):
    """Body khi mở phiên chat mới — `title` tuỳ chọn, thiếu thì lấy câu hỏi đầu."""

    title = serializers.CharField(required=False, allow_blank=True, max_length=200)
    question = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def create(self, validated_data):
        title = (validated_data.get("title") or "").strip()
        if not title:
            question = (validated_data.get("question") or "").strip()
            title = question[:200] if question else ""
        return AIChatSession.objects.create(user=self.context["request"].user, title=title)
