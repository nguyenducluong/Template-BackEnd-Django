from django.utils.translation import gettext as _
from rest_framework import serializers


class AIChatMessageSerializer(serializers.Serializer):
    """One message in the conversation history sent to the AI."""

    role = serializers.ChoiceField(choices=["user", "assistant", "system"])
    content = serializers.CharField(allow_blank=False, trim_whitespace=True)


class AIChatRequestSerializer(serializers.Serializer):
    """Payload for POST /api/v1/ai/chat/."""

    messages = AIChatMessageSerializer(many=True, min_length=1, max_length=50)

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
