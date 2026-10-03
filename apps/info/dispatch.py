"""
Dispatcher duy nhất của app `info` — ``POST /api/v1/info/dispatch``.

Body (JSON, hoặc multipart với ``data``/``params`` là JSON string):

    {
        "resource": "group_headers" | "page_headers" | "system_headers" | "headers",
        "action":   "list" | "retrieve" | "structure"
                    | "create" | "update" | "delete" | "reorder",
        "id":       12,        # bắt buộc với retrieve/update/delete
        "data":     {...},     # bắt buộc với create/reorder (update thì tuỳ)
        "params":   {...}      # list/retrieve/structure: page, per_page, search,
                               # order_by, filters, scope...
    }

Đây là bản thay thế ĐÚNG cho danh sách endpoint CRUD cũ (PUT/PATCH/DELETE):

    ❌ GET    /api/v1/info/group-headers            → POST {resource:'group_headers', action:'list'}
    ❌ GET    /api/v1/info/group-headers/{id}       → POST {..., action:'retrieve', id}
    ❌ POST   /api/v1/info/group-headers            → POST {..., action:'create', data}
    ❌ PUT    /api/v1/info/group-headers/{id}       → POST {..., action:'update', id, data}
    ❌ PATCH  /api/v1/info/group-headers/{id}       → POST {..., action:'update', id, data:{partial:true}}
    ❌ DELETE /api/v1/info/group-headers/{id}       → POST {..., action:'delete', id}
    (tương tự cho `page_headers`, `system_headers`)
    ❌ GET    /api/v1/info/headers/structure        → POST {resource:'headers', action:'structure'}
                                                       (+ params.scope = 'registered' | 'all')

Quy ước: KHÔNG dùng PUT / PATCH / DELETE — xem ``libs/http_policy.py``.
"""

import logging

from django.db import DEFAULT_DB_ALIAS, router, transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from libs.responses import created_response, error_response, success_response

from . import services
from .models import GroupHeader, PagesHeader, SystemHeader
from .permissions import get_user_permitted_header_ids
from .serializers import GroupHeaderSerializer, PagesHeaderSerializer, SystemHeaderSerializer

logger = logging.getLogger("apps")

# ---- Hằng số --------------------------------------------------------------
READ_ACTIONS = ("list", "retrieve", "structure")
WRITE_ACTIONS = ("create", "update", "delete", "reorder")

# `headers` không phải CRUD — chỉ phục vụ action `structure`.
STRUCTURE_RESOURCE = "headers"
STRUCTURE_SCOPES = ("registered", "all")

MAX_PER_PAGE = 200
DEFAULT_PER_PAGE = 20

# Cấu hình từng resource: model, serializer, field cho phép GHI (chống
# mass-assignment), field lọc/tìm/sắp xếp cho phép.
RESOURCES = {
    "group_headers": {
        "model": GroupHeader,
        "serializer": GroupHeaderSerializer,
        "label": "Group headers",
        "write_fields": ("sort", "is_use", "group_vi", "group_en", "group_kr"),
        "order_by": ("sort", "id"),
        "search_fields": ("group_vi", "group_en", "group_kr"),
        "filters": {"is_use": "is_use"},
        "select_related": (),
        "permission_filter": False,
    },
    "page_headers": {
        "model": PagesHeader,
        "serializer": PagesHeaderSerializer,
        "label": "Page headers",
        "write_fields": ("group_header", "sort", "is_use", "page_vi", "page_en", "page_kr"),
        "order_by": ("sort", "id"),
        "search_fields": ("page_vi", "page_en", "page_kr"),
        "filters": {"group_header": "group_header_id", "is_use": "is_use"},
        "select_related": ("group_header",),
        "permission_filter": False,
    },
    "system_headers": {
        "model": SystemHeader,
        "serializer": SystemHeaderSerializer,
        "label": "System headers",
        "write_fields": (
            "page_header", "sort", "is_use", "is_mobile",
            "view_vi", "view_en", "view_kr",
            "header_vi", "header_en", "header_kr",
        ),
        "order_by": ("sort", "id"),
        "search_fields": ("view_vi", "view_en", "view_kr", "header_vi", "header_en", "header_kr"),
        "filters": {"page_header": "page_header_id", "is_use": "is_use"},
        "select_related": ("page_header",),
        # Quyền T1: user chỉ đọc header mình được cấp (trừ khi scope='all' + có quyền ghi).
        "permission_filter": True,
    },
}


def requires_write_permission(resource, action, params=None) -> bool:
    """True nếu request cần quyền GHI cấu hình (``CanWriteInfoConfig``)."""
    if action in WRITE_ACTIONS:
        return True
    # Cây menu ĐẦY ĐỦ (mọi header) là dữ liệu quản trị.
    return action == "structure" and str((params or {}).get("scope") or "registered").lower() == "all"


# ---- Tiện ích -------------------------------------------------------------

def _coerce_bool(value) -> bool:
    """Chấp nhận True/1/"true"/"1"/"yes" (multipart gửi mọi thứ dạng chuỗi)."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def _model_field_names(config) -> set:
    """Tên các field thật của model (dùng whitelist khi sắp xếp)."""
    return {field.name for field in config["model"]._meta.get_fields()}


def _clean_ordering(raw, config) -> list:
    """Chỉ cho phép sắp xếp theo field có thật (chống order_by tuỳ ý)."""
    allowed = _model_field_names(config)
    ordering = []
    for token in str(raw or "").split(","):
        token = token.strip()
        if token and token.lstrip("-") in allowed:
            ordering.append(token)
    return ordering or list(config["order_by"])


def _paginate(queryset, params) -> tuple:
    """Phân trang thủ công, trả meta giống ``libs.pagination.StandardPagination``."""
    from django.core.paginator import Paginator

    try:
        per_page = int(params.get("per_page") or DEFAULT_PER_PAGE)
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE
    per_page = max(1, min(per_page, MAX_PER_PAGE))

    try:
        page_number = int(params.get("page") or 1)
    except (TypeError, ValueError):
        page_number = 1
    page_number = max(1, page_number)

    paginator = Paginator(queryset, per_page)
    page = paginator.page(min(page_number, paginator.num_pages or 1))
    meta = {
        "page": page.number,
        "per_page": per_page,
        "total": paginator.count,
        "total_pages": paginator.num_pages,
        "has_next": page.has_next(),
        "has_previous": page.has_previous(),
    }
    return list(page.object_list), meta


def _clean_write_data(config, data):
    """Lọc ``data`` theo whitelist field ghi được (chống mass-assignment).

    Trả ``None`` khi không có field nào hợp lệ.
    """
    if not isinstance(data, dict):
        return None
    clean = {key: value for key, value in data.items() if key in config["write_fields"]}
    return clean or None


def _get_object(config, item_id):
    """Lấy object theo id (trả ``None`` nếu không tồn tại)."""
    if not item_id:
        return None
    return config["model"].objects.filter(pk=item_id).first()


# ---- Action ĐỌC -----------------------------------------------------------

def _handle_list(config, user, params):
    """LIST — phân trang + lọc + tìm kiếm + sắp xếp (whitelist)."""
    queryset = config["model"].objects.all()
    if config.get("select_related"):
        queryset = queryset.select_related(*config["select_related"])

    # Quyền T1: user chỉ thấy header được cấp (trừ khi xin scope='all' + có quyền ghi).
    if config.get("permission_filter") and str(params.get("scope") or "").lower() != "all":
        queryset = queryset.filter(id__in=get_user_permitted_header_ids(user))

    filters = params.get("filters") if isinstance(params.get("filters"), dict) else {}
    for param_name, field_name in config["filters"].items():
        value = params.get(param_name, filters.get(param_name))
        if value is None or value == "":
            continue
        queryset = queryset.filter(**{field_name: _coerce_bool(value) if field_name == "is_use" else value})

    search = str(params.get("search") or "").strip()
    if search and config.get("search_fields"):
        condition = Q()
        for field_name in config["search_fields"]:
            condition |= Q(**{f"{field_name}__icontains": search})
        queryset = queryset.filter(condition)

    queryset = queryset.order_by(*_clean_ordering(params.get("order_by"), config))
    items, page_meta = _paginate(queryset, params)
    return success_response(
        data=config["serializer"](items, many=True).data,
        message=_(config["label"]),
        meta={**page_meta, "status_code": 200},
    )


def _handle_retrieve(config, user, item_id):
    """RETRIEVE — 1 bản ghi theo id (tôn trọng quyền T1 với system_headers)."""
    instance = _get_object(config, item_id)
    if instance is None:
        return error_response(message=_("Resource not found"), status=404)
    if config.get("permission_filter") and item_id not in get_user_permitted_header_ids(user):
        return error_response(message=_("You do not have permission to access this system header."), status=403)
    return success_response(data=config["serializer"](instance).data, message=_(config["label"]))


def _handle_structure(user, params, language):
    """STRUCTURE — cây menu 3 cấp (``scope=registered`` cho user, ``all`` cho quản trị)."""
    scope = str(params.get("scope") or "registered").lower()
    if scope not in STRUCTURE_SCOPES:
        return error_response(message=_("Field 'scope' must be 'registered' or 'all'."), status=400)

    # scope='all' cần quyền ghi cấu hình — đã kiểm tra ở view (requires_write_permission).
    data = services.get_full_structure(language) if scope == "all" else services.get_registered_structure(user, language)
    return success_response(data=data, message=_("Header structure"), meta={"status_code": 200, "scope": scope})


# ---- Action GHI (chỉ tới đây khi đã qua CanWriteInfoConfig) ---------------

def _handle_create(config, user, data):
    """CREATE — thay POST của REST CRUD cũ."""
    clean = _clean_write_data(config, data)
    if clean is None:
        return error_response(message=_("No writable field provided."), status=400)
    serializer = config["serializer"](data=clean)
    if not serializer.is_valid():
        return error_response(message=_("Invalid data provided"), errors=serializer.errors, status=400)

    instance = serializer.save()
    logger.info("info.dispatch create resource=%s id=%s user=%s", config["label"], instance.pk, getattr(user, "id", None))
    return created_response(data=config["serializer"](instance).data, message=_("Resource created successfully"))


def _handle_update(config, user, item_id, data):
    """UPDATE — thay cả PUT và PATCH (``data.partial = true`` → partial update)."""
    instance = _get_object(config, item_id)
    if instance is None:
        return error_response(message=_("Resource not found"), status=404)

    clean = _clean_write_data(config, data)
    if clean is None:
        return error_response(message=_("No writable field provided."), status=400)

    serializer = config["serializer"](instance, data=clean, partial=_coerce_bool(data.get("partial")))
    if not serializer.is_valid():
        return error_response(message=_("Invalid data provided"), errors=serializer.errors, status=400)

    serializer.save()
    logger.info("info.dispatch update resource=%s id=%s partial=%s user=%s", config["label"], instance.pk, _coerce_bool(data.get("partial")), getattr(user, "id", None))
    return success_response(data=serializer.data, message=_("Updated successfully"))


def _handle_delete(config, user, item_id):
    """DELETE — thay DELETE của REST CRUD cũ."""
    instance = _get_object(config, item_id)
    if instance is None:
        return error_response(message=_("Resource not found"), status=404)

    deleted_id = instance.pk
    instance.delete()
    logger.info("info.dispatch delete resource=%s id=%s user=%s", config["label"], deleted_id, getattr(user, "id", None))
    # 200 + envelope (KHÔNG dùng 204: EncryptionMiddleware bỏ qua response 204
    # ⇒ client mã hóa sẽ nhận body rỗng không giải mã được).
    return success_response(data={"id": deleted_id, "deleted": True}, message=_("Deleted successfully"))


def _handle_reorder(config, user, data):
    """REORDER — cập nhật ``sort`` theo đúng thứ tự id client gửi lên."""
    order = data.get("order") if isinstance(data, dict) else None
    if not isinstance(order, list) or not order:
        return error_response(message=_("Field 'order' must be a non-empty array of ids."), status=400)
    try:
        ids = [int(item) for item in order]
    except (TypeError, ValueError):
        return error_response(message=_("Field 'order' must contain integers only."), status=400)

    model = config["model"]
    updated = 0
    # Mở transaction trên ĐÚNG alias của model. Dự án dùng PostgreSQL
    # multi-schema: `atomic()` không tham số sẽ mở trên `default` còn query
    # chạy trên `schema_info` ⇒ rollback/ghi không atomic thật sự.
    with transaction.atomic(using=router.db_for_write(model) or DEFAULT_DB_ALIAS):
        for index, pk in enumerate(ids, start=1):
            updated += model.objects.filter(pk=pk).update(sort=index)

    logger.info("info.dispatch reorder resource=%s ids=%s updated=%s user=%s", config["label"], len(ids), updated, getattr(user, "id", None))
    return success_response(data={"requested": len(ids), "updated": updated}, message=_("Updated successfully"))


# ---- Entry point ----------------------------------------------------------

def handle(resource, action, user, item_id=None, data=None, params=None, language="vi"):
    """Chạy 1 action của dispatcher — LUÔN trả envelope (không raise)."""
    params = params if isinstance(params, dict) else {}
    data = data if isinstance(data, dict) else {}

    if resource == STRUCTURE_RESOURCE:
        if action != "structure":
            return error_response(message=_("Resource 'headers' only supports action 'structure'."), status=400)
        return _handle_structure(user, params, language)

    config = RESOURCES.get(resource)
    if config is None:
        return error_response(message=_("Unknown resource '%(resource)s'.") % {"resource": resource}, status=400)

    if action in READ_ACTIONS:
        if action == "structure":
            return _handle_structure(user, params, language)
        if action == "retrieve":
            return _handle_retrieve(config, user, item_id)
        return _handle_list(config, user, params)

    if action == "create":
        return _handle_create(config, user, data)
    if action == "update":
        return _handle_update(config, user, item_id, data)
    if action == "delete":
        return _handle_delete(config, user, item_id)
    if action == "reorder":
        return _handle_reorder(config, user, data)

    # Không tới được đây (serializer đã whitelist action) — phòng thủ.
    return error_response(message=_("Unknown action '%(action)s'.") % {"action": action}, status=400)



