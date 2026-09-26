"""
ViewSet chuẩn của dự án — chỉ GET / POST / OPTIONS.

``PostOnlyModelViewSet`` = list + retrieve + create + update + destroy, nhưng
mọi thao tác GHI đều gọi qua POST (``.../{id}/update`` và ``.../{id}/delete``
do ``libs.routers.PostOnlyRouter`` sinh ra). PUT / PATCH / DELETE không nằm
trong ``http_method_names`` nên bị DRF trả 405, và cũng bị
``MethodPolicyMiddleware`` chặn từ trước ở tầng middleware.

Dùng cho CRUD mới thay cho ``viewsets.ModelViewSet``:

    from libs.routers import PostOnlyRouter
    from libs.viewsets import PostOnlyModelViewSet

    router = PostOnlyRouter(trailing_slash=False)
    router.register(r"things", ThingViewSet, basename="thing")
"""

from rest_framework import mixins, viewsets

from libs.responses import EnvelopeMixin

# Giá trị "partial" được coi là True khi client gửi lên (JSON có thể là bool
# hoặc chuỗi nếu request đi dạng multipart).
_TRUTHY = {"1", "true", "yes", "y", "on"}


def _is_partial_request(request) -> bool:
    """True nếu body của request yêu cầu partial update (thay PATCH)."""
    data = getattr(request, "data", None)
    if not hasattr(data, "get"):
        return False
    value = data.get("partial")
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in _TRUTHY


class PostOnlyUpdateMixin:
    """``POST .../{id}/update`` phục vụ cả full update và partial update."""

    def update(self, request, *args, **kwargs):
        # DRF đọc ``partial`` từ kwargs (mặc định False = full update).
        kwargs["partial"] = _is_partial_request(request)
        return super().update(request, *args, **kwargs)


class PostOnlyModelViewSet(
    PostOnlyUpdateMixin,
    EnvelopeMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    CRUD đầy đủ nhưng chỉ expose GET / POST / OPTIONS.

    - list     : GET  /resource
    - create   : POST /resource
    - retrieve : GET  /resource/{id}
    - update   : POST /resource/{id}/update   (body ``{"partial": true}`` → PATCH-like)
    - destroy  : POST /resource/{id}/delete
    """

    http_method_names = ["get", "post", "options"]


class PostOnlyReadOnlyModelViewSet(
    EnvelopeMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Chỉ đọc (list + retrieve) — tương đương ``ReadOnlyModelViewSet`` nhưng có envelope."""

    http_method_names = ["get", "post", "options"]
