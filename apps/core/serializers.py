from rest_framework import serializers


class BaseSerializer(serializers.ModelSerializer):
    """
    Base serializer with common functionality.
    - Automatically handles UUID field
    - Provides consistent error format
    """

    id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)