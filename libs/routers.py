"""
Router chỉ dùng POST cho mọi thao tác GHI (thay PUT / PATCH / DELETE).

``SimpleRouter`` mặc định sinh ra:

    GET    /resource            → list
    POST   /resource            → create
    GET    /resource/{id}       → retrieve
    PUT    /resource/{id}       → update          ❌ bị cấm
    PATCH  /resource/{id}       → partial_update  ❌ bị cấm
    DELETE /resource/{id}       → destroy         ❌ bị cấm

``PostOnlyRouter`` thay bằng:

    GET    /resource            → list
    POST   /resource            → create
    GET    /resource/{id}       → retrieve
    POST   /resource/{id}/update → update            (thay PUT và PATCH)
    POST   /resource/{id}/delete → destroy           (thay DELETE)

Partial update: gửi ``"partial": true`` trong body của ``.../update``
(xem ``libs.viewsets.PostOnlyUpdateMixin``).

Dùng router này cho MỌI router đăng ký viewset mới trong dự án.
"""

from rest_framework.routers import DynamicRoute, Route, SimpleRouter


class PostOnlyRouter(SimpleRouter):
    """SimpleRouter đã loại bỏ hoàn toàn PUT / PATCH / DELETE."""

    routes = [
        # Collection: GET = list, POST = create
        Route(
            url=r"^{prefix}{trailing_slash}$",
            mapping={"get": "list", "post": "create"},
            name="{basename}-list",
            detail=False,
            initkwargs={"suffix": "List"},
        ),
        # @action(detail=False) — giữ nguyên, khai methods=["get"] hoặc ["post"]
        DynamicRoute(
            url=r"^{prefix}/{url_path}{trailing_slash}$",
            name="{basename}-{url_name}",
            detail=False,
            initkwargs={},
        ),
        # POST thay PUT/PATCH
        Route(
            url=r"^{prefix}/{lookup}/update{trailing_slash}$",
            mapping={"post": "update"},
            name="{basename}-update",
            detail=True,
            initkwargs={"suffix": "Update"},
        ),
        # POST thay DELETE
        Route(
            url=r"^{prefix}/{lookup}/delete{trailing_slash}$",
            mapping={"post": "destroy"},
            name="{basename}-delete",
            detail=True,
            initkwargs={"suffix": "Delete"},
        ),
        # Detail: chỉ còn GET = retrieve
        Route(
            url=r"^{prefix}/{lookup}{trailing_slash}$",
            mapping={"get": "retrieve"},
            name="{basename}-detail",
            detail=True,
            initkwargs={"suffix": "Instance"},
        ),
        # @action(detail=True) — khai methods=["get"] hoặc ["post"]
        DynamicRoute(
            url=r"^{prefix}/{lookup}/{url_path}{trailing_slash}$",
            name="{basename}-{url_name}",
            detail=True,
            initkwargs={},
        ),
    ]
