from rest_framework import serializers
from .models import FaceEmbedding
from apps.accounts.models import User


class FaceRegisterSerializer(serializers.Serializer):
    image = serializers.ImageField()


class FaceSearchSerializer(serializers.Serializer):
    image = serializers.ImageField()
    threshold = serializers.FloatField(default=0.6, min_value=0.0, max_value=1.0)


class FaceVerifySerializer(serializers.Serializer):
    image = serializers.ImageField()
    user_id = serializers.IntegerField()


class FaceMatchSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    full_name = serializers.CharField()
    gen_id = serializers.CharField()
    similarity = serializers.FloatField()