"""
Chính sách HTTP method của API — CHỈ dùng GET / POST / OPTIONS.

Quy ước dự án (xem README mục "Quy ước HTTP method"):

    ┌────────────────────────────────────────────────────────────────────┐
    │  ĐỌC dữ liệu          → GET   /api/v1/...                          │
    │  GHI / thay đổi dữ liệu → POST /api/v1/...  (action trong body)     │
    │  KHÔNG dùng PUT / PATCH / DELETE (kể cả partial update)            │
    └────────────────────────────────────────────────────────────────────┘

Vì sao gom hết về POST:
    1. Mọi mutation đều đi qua lớp mã hóa AES-GCM + middleware giải mã body
       (PUT/PATCH/DELETE body không được middleware giải mã ⇒ lệch contract).
    2. Chỉ còn 1 đường vào cho audit/throttle/log — dễ kiểm soát hơn 5 method.
    3. FE chỉ có 2 hàm `axios_get` / `axios_post` (xem STD/src/axios/axios.jsx),
       khớp 1-1 với 2 method được phép ⇒ không thể "lỡ tay" dùng PUT/DELETE.
    4. Tránh `partial_update` (PATCH) khó kiểm soát validate: thay bằng
       `POST .../update` với cờ `"partial": true` trong body.

Cơ chế cưỡng chế (3 lớp, defense in depth):
    1. ``libs.middlewares.method_policy.MethodPolicyMiddleware`` → 405 + envelope.
    2. Mỗi view khai ``http_method_names`` (BaseViewSet / PostOnlyModelViewSet
       / APIView trong apps.* đều đã khai) và ``PostOnlyRouter`` chỉ sinh route POST.
    3. Proxy allow-list (nginx ``limit_except`` / Apache ``<LimitExcept>``).
"""

# Method DUY NHẤT được phép trên API.
ALLOWED_METHODS = frozenset({"GET", "POST", "OPTIONS"})

# Giá trị header Allow trả về kèm 405 (giữ thứ tự đọc được cho client).
ALLOWED_METHODS_HEADER = "GET, POST, OPTIONS"

# Chỉ áp policy cho các path API. /admin/, /api/docs/... của Django/DRF dùng
# method riêng (chỉ GET/POST) nên không cần chặn ở đây.
PROTECTED_PREFIXES = ("/api/",)
EXCLUDED_PREFIXES = ("/api/docs", "/api/redoc", "/api/schema")


def is_method_allowed(method: str) -> bool:
    """True nếu *method* (vd ``"POST"``) nằm trong danh sách được phép."""
    return str(method or "").upper() in ALLOWED_METHODS


def is_protected_path(path: str) -> bool:
    """True nếu *path* thuộc phạm vi API phải kiểm tra method."""
    path = (path or "").lower()
    if any(path.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
        return False
    return any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)
