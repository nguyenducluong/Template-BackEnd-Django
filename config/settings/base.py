"""
Base Django settings for the project.
All environment-specific settings inherit from this.
"""
import os
from datetime import timedelta
from pathlib import Path

import environ

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
env.read_env(os.path.join(BASE_DIR, ".env"))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-change-me-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*"])

# Application definition
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "django_filters",
    "channels",
]

LOCAL_APPS = [
    "apps.core",
    "apps.accounts",
    "apps.api",
    "apps.face",
    "apps.websocket",
    "apps.info",
    "apps.ai",
    "apps.systems",
    "apps.messages",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Nén response (giảm băng thông cho payload lớn như cây menu/system details)
    "django.middleware.gzip.GZipMiddleware",
    # Chính sách POST-only: chặn PUT/PATCH/DELETE trên /api/ (libs/http_policy.py)
    "libs.middlewares.method_policy.MethodPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "libs.middlewares.rate_limit.RateLimitMiddleware",
    "libs.middlewares.encryption.EncryptionMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "libs.middlewares.language.LanguageMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases
DATABASES = {
    "default": {
        "ENGINE": env("DB_ENGINE", default="django.db.backends.postgresql"),
        "NAME": env("DB_NAME", default="django_api"),
        "USER": env("DB_USER", default="postgres"),
        "PASSWORD": env("DB_PASSWORD", default="postgres"),
        "HOST": env("DB_HOST", default="localhost"),
        "PORT": env("DB_PORT", default="5432"),
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
        "OPTIONS": {},
    }
}

# pgvector (PostgreSQL vector similarity search for face embeddings).
# Must be False on non-PostgreSQL backends (e.g. SQLite in development).
USE_PGVECTOR = env.bool("USE_PGVECTOR", default=True)

# Database Schema Routing
# Map "app_label.model_name" to a PostgreSQL schema. Mỗi app được tách riêng
# schema để "phân vùng theo nghiệp vụ":
#
#   accounts -> "user"      (bảng user, jwt blacklist)
#   face     -> "face_id"   (face embeddings)
#   info     -> "info"      (organization hierarchy, header menu, permissions)
#
# QUAN TRỌNG — vì sao phải đặt search_path = TẤT CẢ schema:
#   - accounts.User có FK tới info.Organization/Shift
#   - info có rất nhiều FK tới accounts.User
#   - face_embeddings có FK tới accounts.User
#   => Các schema phải "nhìn thấy" nhau. Vì vậy mỗi connection của một schema
#      đặt search_path = [schema của nó] + [tất cả schema khác]. Bảng still được
#      TẠO vào đúng schema của nó (sẽ đứng đầu search_path), còn FK chéo resolve
#      được qua các schema còn lại. Đây là "phân vùng theo app", KHÔNG phải cô
#      lập bảo mật (mọi connection vẫn đọc được toàn bộ schema).
#
# LƯU Ý: schema tên "user" là keyword reserved của PostgreSQL → phải quote khi
# dùng trong search_path và CREATE SCHEMA.
DB_DEFAULT_SCHEMA = env("DB_DEFAULT_SCHEMA", default="public")
DB_SCHEMAS = {
    # accounts
    "accounts.user": "user",
    "accounts.jwtblacklist": "user",
    # PHIÊN REFRESH — cùng schema `user` với User.
    # KHÔNG map ⇒ SchemaRouter trả "no opinion" ⇒ bảng `_0042_refresh_token_session`
    # bị tạo ở schema `public` (DB_DEFAULT_SCHEMA), tách rời khỏi `_0010_user`.
    # Dù chạy được (search_path có cả 2) thì mất tính nhất quán: purge task, index
    # và backup đều phải biết bảng này nằm ở đâu.
    "accounts.refreshtokensession": "user",
    # face
    "face.faceembedding": "face_id",
    # info
    "info.organization": "info",
    "info.shift": "info",
    "info.vendor": "info",
    "info.material": "info",
    "info.groupheader": "info",
    "info.pagesheader": "info",
    "info.systemheader": "info",
    "info.systempower": "info",
    "info.headerregistration": "info",
    "info.userheaderregistration": "info",
    "info.headerorganization": "info",
    "info.headerorganizationuserregistration": "info",
    "info.systempermission": "info",
    "info.usersystempermissionregistration": "info",
    # ---- Framework tables (admin/auth/sessions) -> schema public ----
    # Nếu không map, SchemaRouter trả "no opinion" trên các schema alias
    # -> bảng auth/sessions bị NHÂN BẢN vào user/info/face_id schemas.
    "auth.user": "public",
    "auth.group": "public",
    "auth.permission": "public",
    "contenttypes.contenttype": "public",
    "sessions.session": "public",
    "admin.logentry": "public",
}

# Set tên schema (đã de-dupe, giữ thứ tự ổn định)
_SCHEMA_ORDER = list(dict.fromkeys(DB_SCHEMAS.values()))
# schema name reserved cần quote
_RESERVED_SCHEMAS = {"user"}


def _schema_token(name: str) -> str:
    """Return quoted identifier nếu tên là reserved keyword."""
    return f'"{name}"' if name in _RESERVED_SCHEMAS else name


def _search_path(*schemas: str) -> str:
    return ",".join(_schema_token(s) for s in schemas)


# search_path cho connection "default": DB_DEFAULT_SCHEMA + tất cả schema app
DATABASES["default"]["OPTIONS"] = {
    **DATABASES["default"].get("OPTIONS", {}),
    "options": f"-c search_path={_search_path(*([DB_DEFAULT_SCHEMA] + _SCHEMA_ORDER))}",
}

# Auto-create ONE connection per schema; search_path = own-first + all others,
# để FK chéo giữa các schema resolve được.
_base_db = DATABASES["default"]
for _schema in _SCHEMA_ORDER:
    if _schema == DB_DEFAULT_SCHEMA:
        continue  # framework tables map về public = default connection
    _others = [s for s in _SCHEMA_ORDER if s != _schema]
    DATABASES[f"schema_{_schema}"] = {
        **_base_db,
        "OPTIONS": {
            **_base_db.get("OPTIONS", {}),
            "options": f"-c search_path={_search_path(_schema, *_others, DB_DEFAULT_SCHEMA)}",
        },
    }

# Database Routers
DATABASE_ROUTERS = ["libs.db_routers.SchemaRouter"]

# ---------------------------------------------------------------------------
# API Payload Encryption (RSA-OAEP handshake + AES-256-GCM session)
# Mặc định: ON khi DJANGO_ENV != "development" — có thể override bằng
# biến môi trường ENABLE_API_ENCRYPTION=True/False (xem .env.example)
# ---------------------------------------------------------------------------
ENABLE_API_ENCRYPTION = env.bool(
    "ENABLE_API_ENCRYPTION",
    default=env("DJANGO_ENV", default="development") != "development",
)
RSA_PRIVATE_KEY_PATH = env("RSA_PRIVATE_KEY_PATH", default="certs/private_key.pem")
RSA_PUBLIC_KEY_PATH = env("RSA_PUBLIC_KEY_PATH", default="certs/public_key.pem")
CRYPTO_SESSION_TTL = env.int("CRYPTO_SESSION_TTL", default=3600)  # seconds
# Max plaintext body the encryption middleware accepts (bytes). Raise for
# large payloads (e.g. 10MB -> 10485760). Rejects oversized encrypted
# requests early instead of buffering unbounded data in RAM.
ENCRYPTION_MAX_BODY_SIZE = env.int("ENCRYPTION_MAX_BODY_SIZE", default=15 * 1024 * 1024)
# Django's own guard must be >= the encryption limit, otherwise request.body
# raises RequestDataTooBig before the middleware can decrypt.
DATA_UPLOAD_MAX_MEMORY_SIZE = max(
    ENCRYPTION_MAX_BODY_SIZE, env.int("DATA_UPLOAD_MAX_MEMORY_SIZE", default=15 * 1024 * 1024)
)
# Allow encrypted JSON uploads (multipart stays plaintext over HTTPS)
DATA_UPLOAD_MAX_NUMBER_FIELDS = env.int("DATA_UPLOAD_MAX_NUMBER_FIELDS", default=2000)
ENCRYPTION_EXCLUDED_PREFIXES = [
    "/admin",
    "/api/v1/health",
    # LƯU Ý: KHÔNG loại trừ /api/v1/crypto — handshake phải được mã hóa request
    # bằng server public key (middleware tự bỏ qua request plaintext như
    # GET /crypto/public_key vì content-type không phải encrypted+json).
    "/static",
    "/media",
    # AI (chat SSE): loai khoi ma hoa 2 chieu de streaming khong vo.
    # Ly do: (1) StreamingHttpResponse doc `response.content` ben trong middleware ->
    # noi dung bi doc sai/rong giua chung; (2) response SSE la khung TEXT lien tuc,
    # khong phai envelope JSON, ma hoa tung frame se vo huong va lam chay nhanh.
    # Chat log khong chua du lieu bi mat; request van duoc xac thuc bang Bearer JWT.
    "/api/v1/ai",    "/api/schema",
    "/api/docs",
    "/api/redoc",
]

# Redis Configuration
REDIS_HOST = env("REDIS_HOST", default="localhost")
REDIS_PORT = env.int("REDIS_PORT", default=6379)
REDIS_USER = env("REDIS_USER", default="")
REDIS_PASSWORD = env("REDIS_PASSWORD", default="")
REDIS_DB_CACHE = env.int("REDIS_DB_CACHE", default=0)
REDIS_DB_CELERY = env.int("REDIS_DB_CELERY", default=1)
# RESP2 (2) hay RESP3 (3) cho channel layer. Redis 6+ hỗ trợ cả hai; Redis 5.x
# CHỈ có RESP2 ⇒ để 2. Đổi sang 3 khi đã nâng Redis lên 6 trở lên.
REDIS_PROTOCOL = env.int("REDIS_PROTOCOL", default=2)
# Timeout (giây) cho socket của channel layer. Phải >= 60 vì channels_redis chờ
# event bằng `BRPOP` có timeout 60s; nếu nhỏ hơn sẽ bị TimeoutError giữa chừng.
REDIS_SOCKET_TIMEOUT = env.int("REDIS_SOCKET_TIMEOUT", default=65)


def _build_redis_url(db: int) -> str:
    """Build Redis URL from individual connection parameters."""
    if REDIS_USER and REDIS_PASSWORD:
        return f"redis://{REDIS_USER}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{db}"
    if REDIS_PASSWORD:
        return f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{db}"
    return f"redis://{REDIS_HOST}:{REDIS_PORT}/{db}"


# Redis Cache
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": _build_redis_url(REDIS_DB_CACHE),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_CLASS": "redis.BlockingConnectionPool",
            "CONNECTION_POOL_KWARGS": {"protocol": 2},  # Local Redis < 6 has no RESP3 (HELLO)
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "timeout": 20,
            },
            "MAX_CONNECTIONS": 1000,
            "PICKLE_VERSION": -1,
        },
        "KEY_PREFIX": "django_api",
    }
}

# Channel Layers (Redis for WebSocket/Channels)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            # `protocol=2` (RESP2) là BẮT BUỘC với Redis < 6.
            #
            # LÝ DO: `redis-py` mặc định dùng RESP3 và mở kết nối bằng lệnh
            # `HELLO 3`. Redis 5.x (bản đi kèm XAMPP) không có lệnh này ⇒ mọi
            # thao tác channel layer ném:
            #     ResponseError: unknown command `HELLO`, with args beginning with: `3`
            # và WebSocket chết ngay ở bước `group_add` (hiện ra là HTTP 403).
            # Nâng Redis lên 6+ thì bỏ được tham số này.
            # Timeout phải truyền trong QUERY STRING của URL (dạng
            # `?socket_timeout=..`), KHÔNG phải keyword riêng — `RedisChannelLayer`
            # chỉ nhận `hosts`, `prefix`, `symmetric_encryption_keys`, `expiry`
            # nên truyền kwarg riêng sẽ ném `TypeError: unexpected keyword argument`.
            #
            # Giá trị phải >= thời gian chờ của `BRPOP` (channels_redis chặn 60s để
            # nghe event); nếu nhỏ hơn, mọi lần nhận event sẽ thành
            # `redis.exceptions.TimeoutError` và socket chết.
            "hosts": [f"{_build_redis_url(REDIS_DB_CACHE)}?protocol={REDIS_PROTOCOL}&socket_connect_timeout={REDIS_SOCKET_TIMEOUT}&socket_timeout={REDIS_SOCKET_TIMEOUT}"],
            "symmetric_encryption_keys": [SECRET_KEY],
        },
    },
}

# Celery Configuration
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=_build_redis_url(REDIS_DB_CELERY))
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=_build_redis_url(REDIS_DB_CELERY))
CELERY_ACCEPT_CONTENT = ["application/json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Ho_Chi_Minh"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BEAT_SCHEDULE = {
    # Dọn JWT blacklist đã hết hạn (bảng _0041_jwt_blacklist) — không có job này
    # thì bảng chỉ tăng theo mỗi lần logout/refresh, không bao giờ được dọn.
    # Dùng số giây (không import celery.schedules) để settings không phụ thuộc celery.
    "accounts-purge-expired-jwt-blacklist": {
        "task": "accounts.purge_expired_jwt_blacklist",
        "schedule": 24 * 60 * 60,  # 1 lần/ngày
    },
    # Dọn phiên refresh token đã hết hạn từ lâu (bảng _0042_refresh_token_session).
    # Bảng này tăng 1 dòng mỗi lần refresh; không có job thì phình vô hạn.
    "accounts-purge-expired-refresh-sessions": {
        "task": "accounts.purge_expired_refresh_sessions",
        "schedule": 24 * 60 * 60,  # 1 lần/ngày
    },
}

# Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "libs.auth.authentication.JWTAuthentication",
    ),
    "UNAUTHENTICATED_USER": "libs.auth.anonymous_user.AnonymousUser",
    "UNAUTHENTICATED_TOKEN": None,
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "crypto_handshake": env("THROTTLE_CRYPTO_HANDSHAKE", default="10/min"),
        "auth": env("THROTTLE_AUTH", default="10/min"),
        # Refresh token được gọi tự động theo vòng đời access token (15 phút)
        # và mỗi lần app quay lại tab. Tách khỏi `auth` để nhiều người dùng
        # cùng IP (văn phòng/NAT) không tự throttle lẫn nhau.
        "auth_refresh": env("THROTTLE_AUTH_REFRESH", default="60/min"),
        "login": env("THROTTLE_LOGIN", default="5/min"),
        "register": env("THROTTLE_REGISTER", default="3/hour"),
        "me": env("THROTTLE_ME", default="60/min"),
        "user_read": env("THROTTLE_USER_READ", default="120/min"),
        "user_write": env("THROTTLE_USER_WRITE", default="30/min"),
        "face": env("THROTTLE_FACE", default="20/min"),
        "core": env("THROTTLE_CORE", default="60/min"),
        "ai": env("THROTTLE_AI", default="60/min"),
        "systems": env("THROTTLE_SYSTEMS", default="120/min"),
        # App info (POST /api/v1/info/dispatch, cây menu hệ thống)
        "info": env("THROTTLE_INFO", default="120/min"),
        # App messages (POST /api/v1/messages/dispatch, chat room kin)
        "messages": env("THROTTLE_MESSAGES", default="120/min"),
        "default": env("THROTTLE_DEFAULT", default="100/min"),
    },
    "DEFAULT_PAGINATION_CLASS": "libs.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ),
    "EXCEPTION_HANDLER": "libs.exceptions.custom_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
    "COERCE_DECIMAL_TO_STRING": True,
    "UPLOADED_FILES_USE_URL": False,
    "DEFAULT_CONTENT_NEGOTIATION_CLASS": "libs.middlewares.content_negotiation.IgnoreLanguageContentNegotiation",
}

# Custom JWT Configuration (replaces djangorestframework-simplejwt)
JWT_AUTH = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_TOKEN_LIFETIME", default=7)),
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_CLAIM": "user_id",
}

# ---------------------------------------------------------------------------
# Refresh token: luoi hai cap (idle + absolute) — xem libs/auth/refresh_tokens.py
# ---------------------------------------------------------------------------
# REFRESH_IDLE_SECONDS: khong dung app trong bao lau thi het phien (mac dinh 7 ngay).
REFRESH_IDLE_SECONDS = env.int("REFRESH_IDLE_SECONDS", default=7 * 24 * 3600)

# REFRESH_ABSOLUTE_SECONDS: phien toi da tu luc LOGIN, KHONG reset khi xoay token
# => dung app lien tuc cung khong keo dai duoc phien vo han (mac dinh 30 ngay).
REFRESH_ABSOLUTE_SECONDS = env.int("REFRESH_ABSOLUTE_SECONDS", default=30 * 24 * 3600)

# So ngay giu ban ghi da het han de doi chieu audit log (0 = xoa ngay).
REFRESH_SESSION_KEEP_DAYS = env.int("REFRESH_SESSION_KEEP_DAYS", default=30)

# Khoang an han cho refresh token vua bi xoay.
#
# DA BO (default=0): luong refresh chuyen sang TOKEN FAMILY (bang
# `_0042_refresh_token_session`), noi trang thai la thuoc tinh cua tung token
# (`revoked_at` + `replaced_by`). Token da xoay ma gui lai = TAI SU DUNG ->
# thu hoi ca family -> 401.
#
# Cach cu "dem nguoc gio" (created_at >= now - 60s) chinh la nguyen nhan goc cua
# loi "token con han 7 ngay bi logout oan": client quay lai app sau 5 phut thi
# vuot 60s. Phan biet bang TRANG THAI dung o moi truong hop, khong con phu thuoc
# thoi gian.
#
# Giu bien nay de rollback an toan ma khong phai revert code.
JWT_REFRESH_REUSE_GRACE_SECONDS = env.int("JWT_REFRESH_REUSE_GRACE_SECONDS", default=0)

# Rate Limiting (Phase 1a)
LOGIN_RATE_LIMIT = env.int("LOGIN_RATE_LIMIT", default=5)  # requests per window
LOGIN_RATE_LIMIT_WINDOW = env.int("LOGIN_RATE_LIMIT_WINDOW", default=60)  # seconds
REGISTER_RATE_LIMIT = env.int("REGISTER_RATE_LIMIT", default=3)  # requests per window
REGISTER_RATE_LIMIT_WINDOW = env.int("REGISTER_RATE_LIMIT_WINDOW", default=3600)  # seconds

# Global request rate limit (Layer 1 middleware) — per client IP.
RATE_LIMIT_GLOBAL_MAX = env.int("RATE_LIMIT_GLOBAL_MAX", default=600)
RATE_LIMIT_GLOBAL_WINDOW = env.int("RATE_LIMIT_GLOBAL_WINDOW", default=60)
ENABLE_GLOBAL_RATE_LIMIT = env.bool("ENABLE_GLOBAL_RATE_LIMIT", default=True)
# Prefix phải khớp path THẬT của URLconf (config/urls.py):
#   health = /api/v1/health, tài liệu = /api/docs + /api/schema + /api/redoc.
# Trước đây ghi /api/health, /docs, /schema → không khớp prefix nào, health check
# của monitoring vẫn bị tính vào rate limit và có thể nhận 429 giả.
RATE_LIMIT_ALWAYS_EXCLUDED = [
    "/admin",
    "/api/v1/health",
    "/static",
    "/media",
    "/api/docs",
    "/api/schema",
    "/api/redoc",
]
# .env chỉ THÊM prefix (không thể làm mất các path bắt buộc ở trên) — dedupe
# bằng dict.fromkeys để giữ thứ tự và tránh trùng (ví dụ /api/v1/crypto).
RATE_LIMIT_EXCLUDED_PREFIXES = list(
    dict.fromkeys(RATE_LIMIT_ALWAYS_EXCLUDED + env.list("RATE_LIMIT_EXCLUDED_PREFIXES", default=[]))
)

# Global rate limit middleware respects these (never double-counts endpoints
# that already have fine-grained throttles). Disable in tests/dev if noisy.
if "/api/v1/crypto" not in RATE_LIMIT_EXCLUDED_PREFIXES:
    RATE_LIMIT_EXCLUDED_PREFIXES.append("/api/v1/crypto")

# AI (chat SSE): loai khoi rate limit GLOBAL (600 req/60s).
# Chat + MCP + Form nhieu request nho; dung thu ngan co the chan nham 1 chat dung giua
# luong. Van con bao ve: DRF ScopedRateThrottle voi scope "ai" tren tung view AI.
if "/api/v1/ai" not in RATE_LIMIT_EXCLUDED_PREFIXES:
    RATE_LIMIT_EXCLUDED_PREFIXES.append("/api/v1/ai")

# Trusted reverse proxies. X-Forwarded-For is ONLY honoured for rate limiting
# when the direct peer (REMOTE_ADDR) is listed here — otherwise clients could
# spoof the header to bypass per-IP limits. Example: ["10.0.0.5", "10.0.0.6"]
TRUSTED_PROXIES = env.list("TRUSTED_PROXIES", default=[])

# Account Lockout (Phase 1d)
ACCOUNT_LOCKOUT_MAX_ATTEMPTS = env.int("ACCOUNT_LOCKOUT_MAX_ATTEMPTS", default=5)
ACCOUNT_LOCKOUT_MINUTES = env.int("ACCOUNT_LOCKOUT_MINUTES", default=15)

# ---------------------------------------------------------------------------
# Chính sách HTTP method (POST-only) — xem libs/http_policy.py
# ---------------------------------------------------------------------------
# Lớp middleware chặn PUT/PATCH/DELETE trên /api/ (mặc định BẬT). Tắt chỉ khi
# thật sự cần tương thích ngược (không khuyến khích).
ENFORCE_HTTP_METHOD_POLICY = env.bool("ENFORCE_HTTP_METHOD_POLICY", default=True)

# ---------------------------------------------------------------------------
# Dispatcher info — POST /api/v1/info/dispatch (apps/info/dispatch.py)
# ---------------------------------------------------------------------------
# Đường GHI cấu hình header (create/update/delete/reorder) mặc định TẮT; chỉ bật
# khi đã có màn hình quản trị và power tương ứng trong `_0033/_0039/_0040`.
INFO_DISPATCH_WRITE_ENABLED = env.bool("INFO_DISPATCH_WRITE_ENABLED", default=False)
# Danh sách power được phép ghi: SystemPower.id hoặc SystemPower.power_en.
INFO_DISPATCH_ALLOWED_POWERS = env.list("INFO_DISPATCH_ALLOWED_POWERS", default=[])
# TTL cache cây menu header theo (user, ngôn ngữ), đơn vị giây.
INFO_STRUCTURE_CACHE_TTL = env.int("INFO_STRUCTURE_CACHE_TTL", default=300)

# CORS Configuration
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://127.0.0.1:3000"])

# URL convention: KHÔNG trailing slash cho API (frontend gọi /api/v1/... không có "/" cuối).
# Lưu ý: /admin, /api/docs, /api/schema phải gõ đúng có "/" (CommonMiddleware không còn tự redirect)
APPEND_SLASH = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = [
    "GET", "POST", "OPTIONS",
]
CORS_ALLOW_HEADERS = [
    "accept", "accept-language", "authorization", "content-type",
    "user-agent", "x-csrftoken", "x-requested-with", "x-api-key",
    "x-session-id",
]

# drf-spectacular (Swagger)
SPECTACULAR_SETTINGS = {
    "TITLE": "Django API Server",
    "DESCRIPTION": "Enterprise-grade Django API Server",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Swagger UI: nút Authorize dùng scheme Bearer do libs/auth/schema.py khai báo
    "SECURITY": [{"bearerAuth": []}],
    "SORT_OPERATIONS": True,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
    },
}

# Internationalization (Multi-language: vi, en, kr)
LANGUAGE_CODE = "vi"  # Default language
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True

# Supported languages: (code, display_name)
LANGUAGES = [
    ("en", "English"),
    ("vi", "Tiếng Việt"),
    ("kr", "한국어"),
]

# Translation file paths
LOCALE_PATHS = [
    BASE_DIR / "locale",
]

# Language cookie settings
LANGUAGE_COOKIE_NAME = "django_language"
LANGUAGE_COOKIE_AGE = 31536000  # 1 year
LANGUAGE_COOKIE_DOMAIN = None
LANGUAGE_COOKIE_PATH = "/"
LANGUAGE_COOKIE_SECURE = False
LANGUAGE_COOKIE_HTTPONLY = True
LANGUAGE_COOKIE_SAMESITE = "Lax"

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ----------------------------------------------------------------------------
# App messages — giới hạn tệp đính kèm chat
# ----------------------------------------------------------------------------
# Ràng buộc THẬT sự nằm ở `apps/messages/services/upload.py`: đo dung lượng từ
# file server nhận được (không tin header client) và kiểm loại file bằng magic
# bytes. Hai giá trị dưới đây là MẶC ĐỊNH cho allow-list đó — đổi ở đây thì
# service tự theo, không cần sửa code.
#
# LƯU Ý VẬN HÀNH: Django KHÔNG tự chặn cỡ file upload (chỉ áp `DATA_UPLOAD_MAX_MEMORY_SIZE`
# cho phần không phải file). Muốn chặn cứng ở tầng web server, xem README
# mục "Quy Ước HTTP Method" — nginx `client_max_body_size` phải >= giá trị lớn
# nhất ở đây, nếu không nginx trả 413 trước khi request tới Django.
CHAT_MAX_IMAGE_BYTES = env.int("CHAT_MAX_IMAGE_BYTES", default=20 * 1024 * 1024)  # 20 MB
CHAT_MAX_FILE_BYTES = env.int("CHAT_MAX_FILE_BYTES", default=100 * 1024 * 1024)  # 100 MB

# Media files
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Authentication
# Using custom User model at apps.accounts.models.User
# (no AUTH_USER_MODEL needed — not a Django auth model)
# Custom JWT auth handled by libs.auth package

# Email Configuration
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=25)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=False)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@example.com")

# ---------------------------------------------------------------------------
# Systems / dialog actions (apps.systems dispatcher)
# ---------------------------------------------------------------------------
# Hành vi mặc định của `submit_form` khi hệ thống CHƯA có nơi lưu dữ liệu:
#   "echo"   → trả success + echo dữ liệu đã nhận (persisted=False) để FE chạy được
#              end-to-end (mặc định ở dev).
#   "reject" → trả 501 Not Implemented (khuyến nghị cho production khi chưa cấu hình).
SYSTEMS_SUBMIT_DEFAULT = env("SYSTEMS_SUBMIT_DEFAULT", default="echo")
# Giới hạn tổng dung lượng file đính kèm cho 1 lần submit (MB) — server tự kiểm tra,
# KHÔNG dựa vào FE. Lưu ý: DATA_UPLOAD_MAX_MEMORY_SIZE của Django chỉ áp cho phần
# non-file, nên file upload cần giới hạn riêng ở đây.
SYSTEMS_UPLOAD_MAX_MB = env.int("SYSTEMS_UPLOAD_MAX_MB", default=15)
# TTL cache quyền header theo user (quyền T1) — key `systems:perm:{user_id}`
# trong apps/info/permissions.py. Đổi quyền qua model sẽ xóa cache ngay bằng
# signal (apps/info/signals.py); TTL chỉ là lớp dự phòng.
SYSTEMS_PERM_CACHE_TTL = env.int("SYSTEMS_PERM_CACHE_TTL", default=60)

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["file"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
        "services": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}

# ---- Password Policy ----
PASSWORD_MAX_AGE_DAYS = env.int("PASSWORD_MAX_AGE_DAYS", default=90)

# ---- AI Assistant (Ollama / generic HTTP backend) ----
# Co the tat chatbot bang AI_CHAT_ENABLED (default False = an toan khi deploy,
# bat lai sau khi da `ollama pull` model chat + model embedding).
# FE doc flag nay de AN nút bot (GET /api/v1/ai/faq, meta.is_enabled).
AI_CHAT_ENABLED = env.bool("AI_CHAT_ENABLED", default=False)

# Embedding cho RAG lich su chat.
# bge-m3: 1024 chieu, ho tro da ngon ngu (vi/en/kr).
# DOI model => PHAI doi AI_EMBEDDING_DIMS cho khop (cot vector trong DB).
AI_EMBEDDING_MODEL = env("AI_EMBEDDING_MODEL", default="bge-m3")
AI_EMBEDDING_DIMS = env.int("AI_EMBEDDING_DIMS", default=1024)
AI_EMBEDDING_TIMEOUT = env.int("AI_EMBEDDING_TIMEOUT", default=30)
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", default="http://localhost:11434")
OLLAMA_MODEL = env("OLLAMA_MODEL", default="gemma4:latest")
# Cold model load (8.9GB gemma4) took ~73s in testing — be generous.
OLLAMA_TIMEOUT = env.int("OLLAMA_TIMEOUT", default=300)
# How long the model stays loaded in memory between calls ("30m", "-1" = forever).
OLLAMA_KEEP_ALIVE = env("OLLAMA_KEEP_ALIVE", default="30m")

# ---- OTP (Forgot / Reset Password) ----
OTP_LENGTH = env.int("OTP_LENGTH", default=6)
OTP_EXPIRY_SECONDS = env.int("OTP_EXPIRY_SECONDS", default=300)  # 5 minutes
OTP_MAX_ATTEMPTS = env.int("OTP_MAX_ATTEMPTS", default=3)
RESET_TOKEN_EXPIRY_SECONDS = env.int("RESET_TOKEN_EXPIRY_SECONDS", default=600)  # 10 minutes