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
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
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
# Disabled entirely when DJANGO_ENV == "development"
# ---------------------------------------------------------------------------
ENABLE_API_ENCRYPTION = env("DJANGO_ENV", default="development") != "development"
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
    "/api/v1/crypto",
    "/static",
    "/media",
    "/api/schema",
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
            "hosts": [_build_redis_url(REDIS_DB_CACHE)],
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
CELERY_TIMEZONE = "Asia/Bangkok"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BEAT_SCHEDULE = {}

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
        "login": env("THROTTLE_LOGIN", default="5/min"),
        "register": env("THROTTLE_REGISTER", default="3/hour"),
        "me": env("THROTTLE_ME", default="60/min"),
        "user_read": env("THROTTLE_USER_READ", default="120/min"),
        "user_write": env("THROTTLE_USER_WRITE", default="30/min"),
        "face": env("THROTTLE_FACE", default="20/min"),
        "core": env("THROTTLE_CORE", default="60/min"),
        "ai": env("THROTTLE_AI", default="10/min"),
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

# Rate Limiting (Phase 1a)
LOGIN_RATE_LIMIT = env.int("LOGIN_RATE_LIMIT", default=5)  # requests per window
LOGIN_RATE_LIMIT_WINDOW = env.int("LOGIN_RATE_LIMIT_WINDOW", default=60)  # seconds
REGISTER_RATE_LIMIT = env.int("REGISTER_RATE_LIMIT", default=3)  # requests per window
REGISTER_RATE_LIMIT_WINDOW = env.int("REGISTER_RATE_LIMIT_WINDOW", default=3600)  # seconds

# Global request rate limit (Layer 1 middleware) — per client IP.
RATE_LIMIT_GLOBAL_MAX = env.int("RATE_LIMIT_GLOBAL_MAX", default=600)
RATE_LIMIT_GLOBAL_WINDOW = env.int("RATE_LIMIT_GLOBAL_WINDOW", default=60)
ENABLE_GLOBAL_RATE_LIMIT = env.bool("ENABLE_GLOBAL_RATE_LIMIT", default=True)
RATE_LIMIT_EXCLUDED_PREFIXES = env.list(
    "RATE_LIMIT_EXCLUDED_PREFIXES",
    default=["/admin", "/api/v1/health", "/static", "/media", "/docs", "/schema"],
)

# Global rate limit middleware respects these (never double-counts endpoints
# that already have fine-grained throttles). Disable in tests/dev if noisy.
RATE_LIMIT_EXCLUDED_PREFIXES += ["/api/v1/crypto"]

# Trusted reverse proxies. X-Forwarded-For is ONLY honoured for rate limiting
# when the direct peer (REMOTE_ADDR) is listed here — otherwise clients could
# spoof the header to bypass per-IP limits. Example: ["10.0.0.5", "10.0.0.6"]
TRUSTED_PROXIES = env.list("TRUSTED_PROXIES", default=[])

# Account Lockout (Phase 1d)
ACCOUNT_LOCKOUT_MAX_ATTEMPTS = env.int("ACCOUNT_LOCKOUT_MAX_ATTEMPTS", default=5)
ACCOUNT_LOCKOUT_MINUTES = env.int("ACCOUNT_LOCKOUT_MINUTES", default=15)

# CORS Configuration
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])
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