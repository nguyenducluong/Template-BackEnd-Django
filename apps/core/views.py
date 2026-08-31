from rest_framework import mixins, viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

from libs.auth.throttling import ScopedRateThrottle
from libs.responses import EnvelopeMixin


class BaseViewSet(
    EnvelopeMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Base viewset with common configuration.
    Only exposes GET, POST, OPTIONS methods.
    - list: GET collection
    - retrieve: GET single item
    - create: POST new item
    - No update, partial_update, destroy
    """

    http_method_names = ["get", "post", "options"]

    # Per-scope rate limiting (Layer 2). By default uses the "core" scope;
    # individual viewsets may override ``throttle_scope`` per endpoint.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "core"

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]