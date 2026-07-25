# Django API Server

Enterprise-grade Django REST API Server with modular architecture, ready for production scaling.

## ðŸ“‹ Má»¥c Lá»¥c

- [Kiáº¿n TrÃºc Tá»•ng Quan](#-kiáº¿n-trÃºc-tá»•ng-quan)
- [YÃªu Cáº§u Há»‡ Thá»‘ng](#-yÃªu-cáº§u-há»‡-thá»‘ng)
- [CÃ i Äáº·t & Cháº¡y](#-cÃ i-Ä‘áº·t--cháº¡y)
- [Cáº¥u TrÃºc ThÆ° Má»¥c Chi Tiáº¿t](#-cáº¥u-trÃºc-thÆ°-má»¥c-chi-tiáº¿t)
- [Danh SÃ¡ch API](#-danh-sÃ¡ch-api)
- [Services Layer](#-services-layer)
- [Libraries (libs)](#-libraries-libs)
- [HÆ°á»›ng Dáº«n PhÃ¡t Triá»ƒn](#-hÆ°á»›ng-dáº«n-phÃ¡t-triá»ƒn)
- [Triá»ƒn Khai Production](#-triá»ƒn-khai-production)
- [CÃ¡c Chá»©c NÄƒng Má»Ÿ Rá»™ng](#-cÃ¡c-chá»©c-nÄƒng-má»Ÿ-rá»™ng)

---

## ðŸ— Kiáº¿n TrÃºc Tá»•ng Quan

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                       Nginx (Reverse Proxy)                  â”‚
â”‚              SSL Termination, Static Files, Load Balancing   â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚                   Gunicorn (WSGI) / Uvicorn (ASGI)           â”‚
â”‚                         Django API Server                    â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â” â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”      â”‚
â”‚       â”‚ Apps    â”‚ â”‚ Services â”‚ â”‚ Libs    â”‚ â”‚ Celery   â”‚      â”‚
â”‚       â”‚ Layer   â”‚ â”‚ Layer    â”‚ â”‚ Layer   â”‚ â”‚ Workers  â”‚      â”‚
â”‚       â””â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”˜ â””â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”˜      â”‚
â”‚            â”‚           â”‚            â”‚           â”‚            â”‚
â”œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¤
â”‚              PostgreSQL (+ pgvector) / Redis                 â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### NguyÃªn Táº¯c Kiáº¿n TrÃºc

1. **API Server Only** â€” KhÃ´ng sá»­ dá»¥ng Django Admin, template rendering. Chá»‰ tráº£ vá» JSON.
2. **Service Layer Pattern** â€” Business logic tÃ¡ch rá»i khá»i Views vÃ  Models.
3. **Modular Apps** â€” Má»—i app lÃ  má»™t module Ä‘á»™c láº­p, dá»… dÃ ng thÃªm/bá»›t.
4. **Async First** â€” Async cho I/O operations (HTTP calls, WebSocket, task queue).
5. **Stateless** â€” JWT authentication, Redis session, khÃ´ng lÆ°u state trÃªn server.
6. **Hard Delete** â€” XÃ³a dá»¯ liá»‡u trá»±c tiáº¿p trong database, khÃ´ng soft delete.

---

## ðŸ“¦ YÃªu Cáº§u Há»‡ Thá»‘ng

| CÃ´ng Cá»¥ | PhiÃªn Báº£n |
|---|---|
| Python | 3.12+ |
| Django | 6.0+ |
| PostgreSQL | 16+ **vá»›i extension pgvector** (optional, SQLite cho dev) |
| Redis | 7+ (cho cache, Celery, Channels) |
| Docker | 24+ (cho production) |

---

## ðŸš€ CÃ i Äáº·t & Cháº¡y

### 1. Clone & CÃ i Äáº·t

```bash
# Clone project
git clone <your-repo-url>
cd django

# Táº¡o virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# CÃ i dependencies
pip install -r requirements/dev.txt
```

### 2. Cáº¥u HÃ¬nh MÃ´i TrÆ°á»ng

```bash
# Copy file .env.example thÃ nh .env
copy .env.example .env   # Windows
cp .env.example .env      # Linux/Mac

# Chá»‰nh sá»­a .env theo nhu cáº§u
```

File `.env` máº«u cho development:

```env
DJANGO_SECRET_KEY=django-insecure-dev-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,*

# SQLite cho development (máº·c Ä‘á»‹nh)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# Hoáº·c PostgreSQL cho production
# DB_ENGINE=django.db.backends.postgresql
# DB_NAME=django_api
# DB_USER=postgres
# DB_PASSWORD=postgres
# DB_HOST=localhost
# DB_PORT=5432

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# pgvector â€” chá»‰ báº­t khi dÃ¹ng PostgreSQL (SQLite dev tá»± táº¯t)
USE_PGVECTOR=True
```

### 3. Cháº¡y Migrations & Táº¡o Superuser

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

### 4. Cháº¡y Development Server

```bash
# Django development server
python manage.py runserver 0.0.0.0:8000

# Hoáº·c dÃ¹ng Makefile
make run
```

Truy cáº­p: http://localhost:8000/api/docs/ (Swagger UI)

---

## ðŸ“ Cáº¥u TrÃºc ThÆ° Má»¥c Chi Tiáº¿t

### 1. `config/` â€” Cáº¥u hÃ¬nh Django

```
config/
â”œâ”€â”€ __init__.py
â”œâ”€â”€ asgi.py              # ASGI config: HTTP + WebSocket (Channels)
â”œâ”€â”€ wsgi.py              # WSGI config: Gunicorn
â”œâ”€â”€ celery.py            # Celery app: async task processing
â”œâ”€â”€ urls.py              # URL routing chÃ­nh
â””â”€â”€ settings/
    â”œâ”€â”€ __init__.py      # Auto-load settings theo DJANGO_ENV
    â”œâ”€â”€ base.py           # Settings chung cho má»i mÃ´i trÆ°á»ng
    â”œâ”€â”€ development.py    # Dev: SQLite, debug toolbar, CORS allow all
    â”œâ”€â”€ staging.py        # Staging: káº¿ thá»«a production + debug
    â””â”€â”€ production.py     # Production: SSL, Sentry (optional guard), DB pool, security
```

**Chi tiáº¿t `config/settings/base.py`:**

| Cáº¥u hÃ¬nh | MÃ´ táº£ |
|---|---|
| `SECRET_KEY` | Tá»« env `DJANGO_SECRET_KEY` |
| `DEBUG` | Tá»« env `DJANGO_DEBUG` |
| `DATABASES` | PostgreSQL máº·c Ä‘á»‹nh, config qua env |
| `CACHES` | Redis cache vá»›i connection pool |
| `CHANNEL_LAYERS` | Redis cho WebSocket/Channels |
| `CELERY_*` | Celery config (broker, serializer, beat) |
| `REST_FRAMEWORK` | JWT auth, pagination, filtering, exception handler |
| `SIMPLE_JWT` | Access token 15 phÃºt, refresh 7 ngÃ y, blacklist |
| `CORS_*` | CORS config, whitelist origins |
| `SPECTACULAR_SETTINGS` | Swagger/ReDoc config |
| `EMAIL_*` | SMTP config |
| `USE_PGVECTOR` | Báº­t/táº¯t pgvector (máº·c Ä‘á»‹nh True; SQLite dev tá»± Ä‘áº·t False) |
| `LOGGING` | Console + Rotating file handler |

**CÃ¡ch chá»n mÃ´i trÆ°á»ng:**

```bash
# Máº·c Ä‘á»‹nh: development
python manage.py runserver

# Production
$env:DJANGO_ENV="production"
python manage.py runserver
```

### 2. `apps/` â€” Django Applications

```
apps/
â”œâ”€â”€ __init__.py
â”œâ”€â”€ core/              # BASE: BaseModel, BaseManager, BaseSerializer, BaseViewSet
â”œâ”€â”€ accounts/          # AUTH: User model, JWT, register, login, logout
â”œâ”€â”€ api/               # API: Routing v1, health check endpoints
â””â”€â”€ face/              # FACE: Face recognition (InsightFace + pgvector)
```

#### `apps/core/` â€” Core System

```python
# apps/core/models.py
class BaseModel(models.Model):
    """Abstract base model cho táº¥t cáº£ models trong há»‡ thá»‘ng."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
```

**LÆ°u Ã½:** BaseModel KHÃ”NG cÃ³ `is_active` vÃ  `is_deleted`. Dá»¯ liá»‡u Ä‘Æ°á»£c xÃ³a trá»±c tiáº¿p (hard delete).

#### `apps/core/views.py` â€” BaseViewSet

```python
class BaseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Base viewset chá»‰ há»— trá»£ GET, POST, OPTIONS.
    - list: GET collection
    - retrieve: GET single item
    - create: POST new item
    KHÃ”NG cÃ³ update, partial_update, destroy.
    """
```

**Táº¥t cáº£ viewsets káº¿ thá»«a `BaseViewSet` sáº½ chá»‰ expose:**
- `GET /api/v1/.../` â€” Danh sÃ¡ch
- `GET /api/v1/.../{id}/` â€” Chi tiáº¿t
- `POST /api/v1/.../` â€” Táº¡o má»›i

#### `apps/accounts/` â€” Authentication & Authorization

| Endpoint | Method | MÃ´ táº£ |
|---|---|---|
| `/api/v1/accounts/auth/register/` | POST | ÄÄƒng kÃ½ user má»›i |
| `/api/v1/accounts/auth/login/` | POST | JWT login |
| `/api/v1/accounts/auth/refresh/` | POST | Refresh access token |
| `/api/v1/accounts/auth/logout/` | POST | Logout (blacklist token) |
| `/api/v1/accounts/auth/me/` | GET/POST | Xem/cáº­p nháº­t profile |
| `/api/v1/accounts/auth/change-password/` | POST | Äá»•i máº­t kháº©u |

**User Model** (matching `_0010_user`):

```python
class User(models.Model):
    id = models.BigAutoField(primary_key=True)
    crt_at = models.DateTimeField(auto_now_add=True)
    upd_at = models.DateTimeField(auto_now=True)
    change_pw_at = models.DateTimeField(auto_now_add=True)

    org = models.ForeignKey(Organization, on_delete=models.PROTECT, db_column="org_id")
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, db_column="shift_id")

    gen_id = models.CharField(max_length=8, unique=True, db_index=True)   # 8 chá»¯ sá»‘
    knox_id = models.CharField(max_length=15, unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=50)
    status = models.PositiveSmallIntegerField(choices=..., default=0)   # 0 waiting / 1 approved / 2 reject / 3 block / 4 deleted
    ip_remember = models.CharField(max_length=15, null=True, blank=True)
    password = models.CharField(max_length=128)
    is_locked = models.BooleanField(default=False)

    class Meta:
        db_table = "_0010_user"
```

Login qua **`gen_id`** (8 chá»¯ sá»‘) hoáº·c **`knox_id`** (giá»‘ng email, khÃ´ng cÃ³ @).

#### `apps/api/` â€” API Infrastructure

- **URL Versioning**: `/api/v1/`, `/api/v2/`
- **Health Check**: `/api/v1/health/`, `/api/v1/health/ready/`, `/api/v1/health/live/`
- **API Docs**: `/api/docs/` (Swagger), `/api/redoc/` (ReDoc)

#### `apps/face/` â€” Face Recognition

```
apps/face/
â”œâ”€â”€ models.py               # FaceEmbedding (pgvector VectorField(512))
â”œâ”€â”€ serializers.py          # FaceRegister/Search/Verify serializers
â”œâ”€â”€ views.py                # FaceRegisterView, FaceSearchView, FaceVerifyView
â”œâ”€â”€ migrations/0002_pgvector.py  # Migration cÃ³ Ä‘iá»u kiá»‡n: cÃ i extension + convert cá»™t
â””â”€â”€ services/face_service.py     # InsightFace extract + tÃ¬m kiáº¿m tÆ°Æ¡ng Ä‘á»“ng
```

- **Model**: `FaceEmbedding.embedding` lÃ  cá»™t `vector(512)` native cá»§a **pgvector** trÃªn PostgreSQL. TrÃªn backend khÃ¡c (SQLite dev) tá»± fallback vá» cá»™t JSON text.
- **TÃ¬m kiáº¿m**: trÃªn PostgreSQL cháº¡y cosine distance (`<=>`) ngay trong DB qua `face_service.find_best_match()`; backend khÃ¡c fallback brute-force Python.
- **MÃ´i trÆ°á»ng**: báº­t/táº¯t báº±ng `USE_PGVECTOR`; migration `0002` lÃ  no-op khi táº¯t.

#### `apps/websocket/` â€” WebSocket

| Consumer | Route | MÃ´ táº£ |
|---|---|---|
| `NotificationConsumer` | `ws/notifications/` | Real-time notifications |
| `ChatConsumer` | `ws/chat/<room_id>/` | Real-time chat |

### 3. `services/` â€” Business Logic Layer

```
services/
â”œâ”€â”€ __init__.py
â”œâ”€â”€ base.py              # BaseService: CRUD operations
â”œâ”€â”€ smtp_service.py      # EmailService: gá»­i email (SMTP, SendGrid, Mailgun, SES)
â”œâ”€â”€ redis_service.py     # RedisService: cache, rate limit, pub/sub, distributed lock
â”œâ”€â”€ curl_service.py      # HTTPService: HTTP client (sync + async)
â”œâ”€â”€ socket_service.py    # SocketService: WebSocket messaging
â”œâ”€â”€ queue_service.py     # QueueService: Celery task dispatch
â””â”€â”€ storage_service.py   # StorageService: file storage (local, S3, GCS, MinIO)
```

#### `services/base.py` â€” BaseService

```python
class BaseService:
    """Base class vá»›i CRUD operations máº·c Ä‘á»‹nh."""
    model = None

    def get(self, id)          # Láº¥y record theo ID
    def get_or_none(self, id)  # Láº¥y hoáº·c None
    def list(self, **filters)  # List vá»›i filters
    def create(self, **kwargs) # Táº¡o má»›i (transaction)
    def update(self, instance, **kwargs) # Cáº­p nháº­t (transaction)
    def delete(self, instance) # XÃ³a cá»©ng (transaction)
    def exists(self, **filters) # Kiá»ƒm tra tá»“n táº¡i
    def count(self, **filters)  # Äáº¿m sá»‘ lÆ°á»£ng
```

#### `services/smtp_service.py` â€” EmailService

```python
class EmailService:
    send_simple(subject, message, recipient_list)           # Text email
    send_html(subject, html_content, recipient_list)        # HTML email
    send_templated(subject, template_name, context, to)     # Template email
    send_with_attachment(subject, message, to, file_path)   # Email vá»›i file Ä‘Ã­nh kÃ¨m
```

#### `services/redis_service.py` â€” RedisService

```python
class RedisService:
    # Cache Operations
    get(key, default)                # Láº¥y tá»« cache
    set(key, value, timeout=300)     # Set cache
    delete(key)                      # XÃ³a cache
    set_many(data, timeout)          # Set nhiá»u key
    get_many(keys)                   # Láº¥y nhiá»u key
    delete_pattern(pattern)          # XÃ³a theo pattern

    # Rate Limiting
    check_rate_limit(key, max_requests, window)  # Kiá»ƒm tra rate limit

    # Distributed Lock
    acquire_lock(lock_key, timeout)  # Acquire lock
    release_lock(lock_key)           # Release lock

    # Pub/Sub
    publish(channel, message)        # Publish message
```

#### `services/curl_service.py` â€” HTTPService

```python
class HTTPService:
    # Sync (requests library)
    get(path, **kwargs)              # HTTP GET
    post(path, **kwargs)             # HTTP POST

    # Async (aiohttp)
    async get_async(path, **kwargs)  # Async GET
    async post_async(path, **kwargs) # Async POST

    # Features: Retry (3 láº§n), Connection Pooling, Logging
```

#### `services/socket_service.py` â€” SocketService

```python
class SocketService:
    send_to_user(user_id, event_type, data)    # Gá»­i Ä‘áº¿n user cá»¥ thá»ƒ
    send_to_group(group_name, event_type, data) # Gá»­i Ä‘áº¿n group
    broadcast(event_type, data)                 # Broadcast toÃ n bá»™
```

#### `services/queue_service.py` â€” QueueService

```python
class QueueService:
    dispatch(task_name, args, kwargs, queue, countdown)  # Gá»­i task theo tÃªn
    dispatch_async(task, args, kwargs, countdown)         # Gá»­i task trá»±c tiáº¿p
    get_task_status(task_id)                              # Kiá»ƒm tra status
    revoke_task(task_id, terminate)                       # Há»§y task
```

#### `services/storage_service.py` â€” StorageService

```python
class StorageService:
    save_file(file_path, content)          # LÆ°u file bytes
    save_uploaded_file(file_path, file)    # LÆ°u uploaded file
    delete_file(file_path)                 # XÃ³a file
    get_file_url(file_path)                # Láº¥y URL
    file_exists(file_path)                 # Kiá»ƒm tra tá»“n táº¡i
    get_file_size(file_path)               # Láº¥y kÃ­ch thÆ°á»›c
```

### 4. `libs/` â€” Shared Libraries

```
libs/
â”œâ”€â”€ __init__.py
â”œâ”€â”€ exceptions.py       # Custom exception handler + custom exceptions
â”œâ”€â”€ responses.py        # Standard response format
â”œâ”€â”€ pagination.py       # Standard pagination
â”œâ”€â”€ auth/               # JWT authentication stack
â”‚   â”œâ”€â”€ jwt_utils.py         # generate_tokens, decode_access_token, blacklist
â”‚   â”œâ”€â”€ authentication.py    # DRF JWTAuthentication (401 chuáº©n, WWW-Authenticate)
â”‚   â”œâ”€â”€ jwt_middleware.py    # Channels JWT middleware cho WebSocket (async-safe)
â”‚   â”œâ”€â”€ password.py          # Password hashing/verify helpers
â”‚   â””â”€â”€ anonymous_user.py    # AnonymousUser (thay django.contrib.auth)
â””â”€â”€ middlewares/
    â”œâ”€â”€ content_negotiation.py
    â””â”€â”€ language.py
```

**JWT WebSocket auth (`libs/auth/jwt_middleware.py`):**

- XÃ¡c thá»±c qua header `Authorization: Bearer <token>` hoáº·c `?token=<token>` trÃªn query string.
- User query cháº¡y trong `database_sync_to_async` â€” an toÃ n vá»›i async event loop.
- Token invalid/háº¿t háº¡n â†’ fallback `AnonymousUser` (consumer tá»± quyáº¿t Ä‘á»‹nh tá»« chá»‘i).

#### `libs/exceptions.py` â€” Exception Handler

```python
# Custom exception handler cho DRF
def custom_exception_handler(exc, context):
    # Tráº£ vá» format JSON thá»‘ng nháº¥t

# Custom exceptions
class ServiceUnavailable(APIException):  # 503
class ValidationError(APIException):     # 400
class ConflictError(APIException):       # 409
class ForbiddenError(APIException):      # 403
class NotFoundError(APIException):       # 404
```

#### `libs/responses.py` â€” Response Format

**Response Format chuáº©n:**

```json
{
  "success": true,
  "data": {},
  "message": "Success",
  "errors": null,
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "total_pages": 5,
    "has_next": true,
    "has_previous": false
  }
}
```

```python
# Helper functions
success_response(data, message, status, meta)    # 200 Success
error_response(message, errors, status, meta)     # 400 Error
created_response(data, message)                   # 201 Created
no_content_response()                              # 204 No Content
```

#### `libs/pagination.py` â€” Pagination

```python
class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "per_page"  # ?per_page=50
    max_page_size = 100
    page_query_param = "page"           # ?page=2
```

---

## ðŸŒ Danh SÃ¡ch API

### Authentication

| Method | Endpoint | Auth | MÃ´ táº£ |
|---|---|---|---|
| POST | `/api/v1/accounts/auth/register/` | No | ÄÄƒng kÃ½ |
| POST | `/api/v1/accounts/auth/login/` | No | ÄÄƒng nháº­p |
| POST | `/api/v1/accounts/auth/refresh/` | No | Refresh token |
| POST | `/api/v1/accounts/auth/logout/` | Yes | ÄÄƒng xuáº¥t |
| GET | `/api/v1/accounts/auth/me/` | Yes | Profile |
| POST | `/api/v1/accounts/auth/me/` | Yes | Cáº­p nháº­t profile |
| POST | `/api/v1/accounts/auth/change-password/` | Yes | Äá»•i máº­t kháº©u |

### Health Check

| Method | Endpoint | MÃ´ táº£ |
|---|---|---|
| GET | `/api/v1/health/` | Health check (DB + Redis) |
| GET | `/api/v1/health/ready/` | Readiness probe |
| GET | `/api/v1/health/live/` | Liveness probe |

### API Documentation

| Method | Endpoint | MÃ´ táº£ |
|---|---|---|
| GET | `/api/docs/` | Swagger UI |
| GET | `/api/redoc/` | ReDoc |
| GET | `/api/schema/` | OpenAPI Schema (JSON) |

### FaceID (Face Recognition)

| Method | Endpoint | Auth | MÃ´ táº£ |
|---|---|---|---|
| POST | `/api/v1/face/register/` | Yes | ÄÄƒng kÃ½ face embedding cho **chÃ­nh user hiá»‡n táº¡i** |
| POST | `/api/v1/face/search/` | Yes | TÃ¬m kiáº¿m user giá»‘ng nháº¥t vá»›i áº£nh face (1:N) |
| POST | `/api/v1/face/verify/` | Yes | Verify face cÃ³ khá»›p vá»›i user chá»‰ Ä‘á»‹nh khÃ´ng (1:1) |

**LÆ°u Ã½:**
- DÃ¹ng InsightFace (ArcFace) â€” 512-dim embedding
- Embedding lÆ°u trong cá»™t `vector(512)` **pgvector** trÃªn PostgreSQL; áº£nh gá»‘c lÆ°u vÃ o `media/faces/`
- Cosine similarity threshold máº·c Ä‘á»‹nh: 0.6 (client cÃ³ thá»ƒ truyá»n `threshold` cho search)
- TrÃªn PostgreSQL, matching cháº¡y trong DB (cosine distance `<=>`); SQLite dev fallback brute-force Python
- **Báº£o máº­t**: cáº£ 3 endpoint Ä‘á»u yÃªu cáº§u JWT; register luÃ´n gáº¯n vá»›i `request.user` (chá»‘ng IDOR)

### Modules

| Module | Base URL | MÃ´ táº£ |
|---|---|---|

---

## ðŸ›  HÆ°á»›ng Dáº«n PhÃ¡t Triá»ƒn

### ThÃªm Model Má»›i

```python
# apps/your_app/models.py
from django.db import models
from apps.core.models import BaseModel

class Product(BaseModel):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # KhÃ´ng cáº§n id, created_at, updated_at â€” káº¿ thá»«a tá»« BaseModel
    # KhÃ´ng cáº§n is_active, is_deleted â€” hard delete

    class Meta:
        db_table = "products"
```

### ThÃªm API Endpoint Má»›i

```python
# apps/your_app/views.py
from apps.core.views import BaseViewSet
from .models import Product
from .serializers import ProductSerializer

class ProductViewSet(BaseViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_fields = ["name", "price"]
    search_fields = ["name"]
```

### ThÃªm Service Má»›i

```python
# services/your_service.py
from services.base import BaseService

class ProductService(BaseService):
    model = Product

    def get_products_by_price_range(self, min_price, max_price):
        return self.model.objects.filter(
            price__gte=min_price,
            price__lte=max_price,
        )
```

### Cháº¡y Tests

```bash
# Smoke tests (script cháº¡y trá»±c tiáº¿p, dÃ¹ng SQLite dev DB)
python tests/smoke_e2e.py   # ToÃ n bá»™ flow DRF: login, me, Ä‘á»•i máº­t kháº©u,
                            # refresh/rotation, logout/blacklist, 401
python tests/smoke_ws.py    # WebSocket JWT middleware: header auth,
                            # query-string auth, anonymous, invalid token

# Cháº¡y unit tests vá»›i pytest (config trong pyproject.toml)
pytest

# Cháº¡y vá»›i coverage
pytest --cov=apps --cov-report=html

# Cháº¡y test cá»¥ thá»ƒ
pytest tests/unit/test_accounts.py -v
```

LÆ°u Ã½: cÃ¡c file `tests/smoke_*.py` Ä‘Æ°á»£c Ä‘áº·t tÃªn `smoke_*` (khÃ´ng pháº£i `*_test.py`) Ä‘á»ƒ pytest khÃ´ng thu nháº§m â€” chÃºng lÃ  script thá»±c thi trá»±c tiáº¿p á»Ÿ module level.

### Code Formatting

```bash
# Format code
black .
isort .

# Kiá»ƒm tra lint
flake8 .
black --check .
isort --check-only .
```

---

## ðŸ³ Triá»ƒn Khai Production

### Docker Compose

```bash
# Build vÃ  start services
docker-compose -f docker/docker-compose.yml up -d

# Kiá»ƒm tra logs
docker-compose -f docker/docker-compose.yml logs -f api

# Dá»«ng services
docker-compose -f docker/docker-compose.yml down
```

### Docker Services

| Service | Port | MÃ´ táº£ |
|---|---|---|
| `api` | 8000 | Django API (Gunicorn) |
| `celery-worker` | â€” | Celery task worker |
| `celery-beat` | â€” | Celery periodic tasks |
| `postgres` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis cache & broker |
| `nginx` | 80/443 | Reverse proxy + SSL |

### Production Checklist

- [ ] Set `DJANGO_DEBUG=False`
- [ ] Set `DJANGO_SECRET_KEY` â€” key máº¡nh, ngáº«u nhiÃªn
- [ ] CÃ i extension **pgvector** trÃªn PostgreSQL (`CREATE EXTENSION vector;` â€” migration `0002` tá»± cháº¡y náº¿u user DB Ä‘á»§ quyá»n)
- [ ] Äáº£m báº£o `USE_PGVECTOR=True` (hoáº·c bá» qua â€” máº·c Ä‘á»‹nh True trÃªn production)
- [ ] Cáº¥u hÃ¬nh PostgreSQL connection pool
- [ ] Set `CORS_ALLOWED_ORIGINS` â€” chá»‰ Ä‘á»‹nh domain cá»¥ thá»ƒ
- [ ] Cáº¥u hÃ¬nh SSL certificate cho Nginx
- [ ] Set `SENTRY_DSN` cho error tracking (sentry-sdk náº±m trong `requirements/prod.txt`; thiáº¿u package app váº«n boot, chá»‰ log warning)
- [ ] Báº­t `SECURE_SSL_REDIRECT`, `HSTS`, `XSS Filter`
- [ ] Táº¡o `docker-compose.prod.yml` riÃªng
- [ ] Thiáº¿t láº­p CI/CD pipeline

---

## ðŸ”§ CÃ¡c Chá»©c NÄƒng Má»Ÿ Rá»™ng

### 1. Multi-Tenancy
- Schema-based: Má»—i tenant má»™t schema PostgreSQL riÃªng
- Row-based: ThÃªm `tenant_id` field vÃ o models
- Domain-based: Routing theo subdomain

### 2. Event-Driven Architecture
```python
# Publish event
RedisService.publish("order.created", {"order_id": "123"})

# Consumer (WebSocket)
# Client nháº­n real-time notification
```

### 3. Caching Strategy
```
CDN (Cloudflare) â†’ Redis Cache â†’ Database Cache
```

### 4. Webhook System
- Incoming: Nháº­n webhook tá»« bÃªn thá»© 3
- Outgoing: Gá»­i webhook Ä‘áº¿n client
- Retry: Exponential backoff
- Signature: HMAC verification

### 5. Async Task Processing
```python
# tasks.py
from celery import shared_task

@shared_task
def send_welcome_email(user_id):
    user = User.objects.get(id=user_id)
    EmailService.send_templated(
        "Welcome!",
        "emails/welcome.html",
        {"user": user},
        [user.email],
    )

# Dispatch
send_welcome_email.delay(user_id=user.id)
```

### 6. Observability
- **Logging**: File + Console, tá»± Ä‘á»™ng rotate
- **Metrics**: Prometheus + Grafana (thÃªm `django-prometheus`)
- **Tracing**: OpenTelemetry (thÃªm `opentelemetry-django`)
- **Error Tracking**: Sentry (sáºµn trong production settings)

### 7. API Rate Limiting
```python
# Trong views
from services.redis_service import RedisService

if not RedisService.check_rate_limit(f"user:{user.id}", 100, 60):
    return Response({"detail": "Rate limit exceeded"}, status=429)
```

### 8. Distributed Lock
```python
# TrÃ¡nh duplicate processing
if RedisService.acquire_lock("process:order:123", timeout=30):
    try:
        process_order(order_id)
    finally:
        RedisService.release_lock("process:order:123")
```

---

## ðŸ“„ License

MIT License

---

## ðŸ¤ Contributing

1. Fork project
2. Táº¡o branch: `git checkout -b feature/your-feature`
3. Commit: `git commit -m 'Add feature'`
4. Push: `git push origin feature/your-feature`
5. Táº¡o Pull Request