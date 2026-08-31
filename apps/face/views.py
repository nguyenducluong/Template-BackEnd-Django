from django.conf import settings
from rest_framework import permissions, status
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from apps.accounts.models import User
from libs.responses import error_response, success_response
from libs.auth.throttling import ScopedRateThrottle

from .models import FaceEmbedding
from .serializers import (
    FaceRegisterSerializer,
    FaceSearchSerializer,
    FaceVerifySerializer,
)
from .services.face_service import face_service

DEFAULT_SIMILARITY_THRESHOLD = 0.6


def _serialize_embedding(embedding):
    """Serialize an embedding for storage according to the active backend.

    pgvector's VectorField accepts a plain list; the SQLite fallback stores
    a JSON-encoded string.
    """
    if getattr(settings, "USE_PGVECTOR", False):
        return list(embedding)
    import json

    return json.dumps([float(v) for v in embedding])


class FaceRegisterView(APIView):
    """Register the current user's face embedding."""

    serializer_class = FaceRegisterSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "face"
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Face"], responses={201: dict, 400: dict})
    def post(self, request):
        serializer = FaceRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.validated_data["image"]

        try:
            embedding = face_service.extract_embedding(image)
        except ValueError as exc:
            return error_response(message=str(exc))

        image_path = face_service.save_face_image(request.user.id, image)
        FaceEmbedding.objects.create(
            user=request.user,
            embedding=_serialize_embedding(embedding),
            image_path=image_path,
        )
        return success_response(
            data={
                "user_id": request.user.id,
                "full_name": request.user.full_name,
                "gen_id": request.user.gen_id,
                "similarity": 1.0,
            },
            status=status.HTTP_201_CREATED,
        )


class FaceSearchView(APIView):
    """Search for the closest matching registered face (1:N)."""

    serializer_class = FaceSearchSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "face"
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Face"], responses={200: dict, 400: dict, 404: dict})
    def post(self, request):
        serializer = FaceSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.validated_data["image"]
        threshold = serializer.validated_data["threshold"]

        try:
            query_embedding = face_service.extract_embedding(image)
        except ValueError as exc:
            return error_response(message=str(exc))

        best_match, best_similarity = face_service.find_best_match(
            query_embedding=query_embedding,
            queryset=FaceEmbedding.objects.filter(is_active=True).select_related("user"),
        )

        if best_match is not None and best_similarity >= threshold:
            user = best_match.user
            return success_response(data={
                "user_id": user.id,
                "full_name": user.full_name,
                "gen_id": user.gen_id,
                "similarity": best_similarity,
            })
        return error_response(
            message="No match found",
            errors={"similarity": best_similarity},
            status=status.HTTP_404_NOT_FOUND,
        )


class FaceVerifyView(APIView):
    """Verify a face image against a specific user's registered faces (1:1)."""

    serializer_class = FaceVerifySerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "face"
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Face"], responses={200: dict, 400: dict, 404: dict})
    def post(self, request):
        serializer = FaceVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image = serializer.validated_data["image"]
        user_id = serializer.validated_data["user_id"]

        user = User.objects.filter(id=user_id).first()
        if user is None:
            return error_response(message="User not found", status=status.HTTP_404_NOT_FOUND)

        try:
            query_embedding = face_service.extract_embedding(image)
        except ValueError as exc:
            return error_response(message=str(exc))

        embeddings = FaceEmbedding.objects.filter(user=user, is_active=True)
        if not embeddings.exists():
            return error_response(
                message="No face registered for this user",
                status=status.HTTP_404_NOT_FOUND,
            )

        best_similarity = face_service.find_best_match(
            query_embedding=query_embedding, queryset=embeddings
        )[1]
        return success_response(data={
            "is_match": best_similarity >= DEFAULT_SIMILARITY_THRESHOLD,
            "similarity": best_similarity,
            "user_id": user.id,
            "full_name": user.full_name,
            "gen_id": user.gen_id,
        })

