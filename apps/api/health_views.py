import os

from django.db import connection
from django.utils.translation import gettext as _

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema


class HealthCheckView(APIView):
    """
    Health check endpoint.
    Returns overall system health status.
    """
    authentication_classes = []
    permission_classes = []
    http_method_names = ["get", "options"]

    @extend_schema(
        tags=["Health"],
        responses={200: dict, 503: dict},
    )
    def get(self, request):
        # Check database
        db_healthy = True
        try:
            connection.ensure_connection()
        except Exception:
            db_healthy = False

        # Check Redis
        redis_healthy = True
        try:
            from django.core.cache import cache
            cache.set("health_check", "ok", 5)
            if cache.get("health_check") != "ok":
                redis_healthy = False
        except Exception:
            redis_healthy = False

        health_data = {
            "status": _("healthy") if (db_healthy and redis_healthy) else _("degraded"),
            "version": "1.0.0",
            "environment": os.getenv("DJANGO_ENV", "development"),
            "checks": {
                "database": _("healthy") if db_healthy else _("unhealthy"),
                "redis": _("healthy") if redis_healthy else _("unhealthy"),
            },
        }

        status_code = status.HTTP_200_OK if (db_healthy and redis_healthy) else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(health_data, status=status_code)


class ReadyCheckView(APIView):
    """
    Readiness probe.
    Indicates if the application is ready to serve traffic.
    """
    authentication_classes = []
    permission_classes = []
    http_method_names = ["get", "options"]

    @extend_schema(
        tags=["Health"],
        responses={200: dict, 503: dict},
    )
    def get(self, request):
        try:
            connection.ensure_connection()
            return Response({"status": _("ready")}, status=status.HTTP_200_OK)
        except Exception:
            return Response({"status": _("not ready")}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class LiveCheckView(APIView):
    """
    Liveness probe.
    Indicates if the application is running.
    """
    authentication_classes = []
    permission_classes = []
    http_method_names = ["get", "options"]

    @extend_schema(
        tags=["Health"],
        responses={200: dict},
    )
    def get(self, request):
        return Response({"status": _("alive")}, status=status.HTTP_200_OK)
