# Django API Server

Enterprise-grade Django REST API Server với kiến trúc modular, sẵn sàng mở rộng trong production.

## Mục Lục

- [Kiến Trúc Tổng Quan](#-kiến-trúc-tổng-quan)
- [Yêu Cầu Hệ Thống](#-yêu-cầu-hệ-thống)
- [Cài Đặt & Chạy](#-cài-đặt--chạy)
- [Database Multi-Schema](#-database-multi-schema)
- [Cấu Trúc Thư Mục Chi Tiết](#-cấu-trúc-thư-mục-chi-tiết)
- [Danh Sách API](#-danh-sách-api)
- [Chính Sách Mật Khẩu & Xác Thực](#-chính-sách-mật-khẩu--xác-thực)
- [Services Layer](#-services-layer)
- [Libraries (libs)](#-libraries-libs)
- [Hướng Dẫn Phát Triển](#-hướng-dẫn-phát-triển)
- [Triển Khai Production](#-triển-khai-production)
- [Các Chức Năng Mở Rộng](#-các-chức-năng-mở-rộng)

---

## Kiến Trúc Tổng Quan

```
┌───────────────────────────────────────────────────────────────────────┐
│                         Nginx (Reverse Proxy)                        │
│                SSL Termination, Static Files, Load Balancing          │
├───────────────────────────────────────────────────────────────────────┤
│                    Gunicorn (WSGI) / Uvicorn (ASGI)                   │
│                          Django API Server                           │
├───────────────────────────────────────────────────────────────────────┤
│        ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐             │
│        │ Apps    │ │ Services │ │ Libs    │ │ Celery   │             │
│        │ Layer   │ │ Layer    │ │ Layer   │ │ Workers  │             │
│        └────┬────┘ └────┬─────┘ └────┬────┘ └────┬─────┘             │
│             │           │            │           │                   │
├───────────────────────────────────────────────────────────────────────┤
│              PostgreSQL (+ pgvector) / Redis                          │
└───────────────────────────────────────────────────────────────────────┘
```

### Nguyên Tắc Kiến Trúc

1. **API Server Only** — Không sử dụng Django Admin, template rendering. Chỉ trả về JSON.
2. **Service Layer Pattern** — Business logic tách rời khỏi Views và Models.
3. **Modular Apps** — Mỗi app là một module độc lập, dễ dàng thêm/bớt.
4. **Async First** — Async cho I/O operations (HTTP calls, WebSocket, task queue).
5. **Stateless** — JWT authentication, Redis session, không lưu state trên server.
6. **Hard Delete** — Xóa dữ liệu trực tiếp trong database, không soft delete.

---

## Yêu Cầu Hệ Thống

| Công Cụ    | Phiên Bản                                                 |
| ---------- | --------------------------------------------------------- |
| Python     | 3.12+                                                     |
| Django     | 6.0+                                                      |
| PostgreSQL | 16+ **với extension pgvector** (optional, SQLite cho dev) |
| Redis      | 7+ (cho cache, OTP, Celery, Channels)                     |
| Docker     | 24+ (cho production)                                      |

---

## Cài Đặt & Chạy

### 1. Clone & Cài Đặt

```bash
# Clone project
git clone <your-repo-url>
cd django

# Tạo virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Cài dependencies
pip install -r requirements/dev.txt
```

### 2. Cấu Hình Môi Trường

```bash
# Copy file .env.example thành .env
copy .env.example .env   # Windows
cp .env.example .env      # Linux/Mac
```

File `.env` mẫu cho development:

```env
DJANGO_SECRET_KEY=django-insecure-dev-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,*

# SQLite cho development (mặc định)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# Hoặc PostgreSQL cho production
# DB_ENGINE=django.db.backends.postgresql
# DB_NAME=django_api
# DB_USER=postgres
# DB_PASSWORD=postgres
# DB_HOST=localhost
# DB_PORT=5432

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# pgvector — chỉ bật khi dùng PostgreSQL (SQLite dev tự tắt)
USE_PGVECTOR=True

# Chính sách mật khẩu & OTP
PASSWORD_MAX_AGE_DAYS=90
OTP_LENGTH=6
OTP_EXPIRY_SECONDS=300
OTP_MAX_ATTEMPTS=3
RESET_TOKEN_EXPIRY_SECONDS=600
```

### 3. Chạy Migrations & Tạo Superuser

```bash
python manage.py makemigrations
python manage.py migrate_schemas     # tạo schema + bảng đúng thứ tự FK
python manage.py seed_data           # seed data đã có sẵn
python manage.py createsuperuser
```

### 4. Chạy Development Server

```bash
python manage.py runserver 0.0.0.0:8000
# hoặc: make run
```

Truy cập: http://localhost:8000/api/docs/ (Swagger UI)

> **Lưu ý PostgreSQL multi-schema:** nếu dùng PostgreSQL, thay lệnh `migrate` ở trên bằng
> `python manage.py migrate_schemas` (xem [Database Multi-Schema](#-database-multi-schema)).

---

## Database Multi-Schema

Dự án tách bảng của từng app vào **PostgreSQL schema riêng** để phân vùng logic rõ ràng:

| App                          | Schema                       | Bảng                                                                            |
| ---------------------------- | ---------------------------- | ------------------------------------------------------------------------------- |
| `accounts`                   | `user`                       | `_0010_user`, `_0041_jwt_blacklist`                                             |
| `face`                       | `face_id`                    | `face_embeddings` (pgvector)                                                    |
| `info`                       | `info`                       | organizations, shift, vendor, material, group/pages/system header, permissions… |
| Khác (core, api, websocket…) | `public` (DB_DEFAULT_SCHEMA) | —                                                                               |

Mapping được khai báo trong `config/settings/base.py`:

```python
DB_SCHEMAS = {
    "accounts.user": "user",
    "accounts.jwtblacklist": "user",
    "face.faceembedding": "face_id",
    "info.organization": "info",
    # ... các model info khác
}
```

### Cách hoạt động

- **`libs/db_routers.py` (`SchemaRouter`)** đọc `DB_SCHEMAS` và route mỗi model tới
  connection tương ứng `schema_<tên>` (VD `schema_user`, `schema_info`, `schema_face_id`).
- **Mỗi connection** được tạo với `search_path` gồm **schema của nó đứng đầu + toàn bộ các schema khác**. Nhờ đó:
  - Bảng được **CREATE** vào đúng schema của app mình (search_path ưu tiên phần tử đầu).
  - **FK chéo app vẫn resolve được** — PostgreSQL tìm thấy bảng referenced nằm trong search_path
    (VD `info._0035_header_registration` → `"user"._0010_user(id)`,
    `face_id.face_embeddings` → `"user"._0010_user(id)`).
- Schema tên `user` là **reserved keyword** của PostgreSQL → mọi chỗ dùng đều được quote
  (`"user"`): `CREATE SCHEMA "user"`, `search_path="user",...`, FK `REFERENCES "user"._0010_user(id)`.

### Chạy migrations

⚠️ **KHÔNG dùng `python manage.py migrate` trực tiếp** khi dùng PostgreSQL multi-schema.
FK chéo app tạo **circular dependency** (accounts.User → info.Organization/Shift và
info.\* → accounts.User), nên phải migrate **theo thứ tự** từng bước:

```bash
python manage.py migrate_schemas
```

Command này (`apps/core/management/commands/migrate_schemas.py`) tự động:

1. **Tạo schema** còn thiếu (`CREATE SCHEMA IF NOT EXISTS`) qua connection `default`.
2. **`migrate accounts 0001`** → tạo `_0010_user` ở schema `user` (chưa có FK tới info).
3. **`migrate info`** → tạo 14 bảng ở schema `info`, FK chéo sang `"user"._0010_user` OK.
4. **`migrate accounts` (0002)** → thêm FK `org_id`/`shift_id` từ `_0010_user` sang `info.*` (đã tồn tại).
5. **`migrate face`** → tạo `face_id.face_embeddings`, FK sang `"user"._0010_user` OK.

Command **idempotent** — chạy lại sẽ no-op an toàn. `manage.py check` dùng để kiểm tra cấu hình.

### Thêm app / model mới

1. Thêm mapping `"app_label.model_name": "schema_x"` vào `DB_SCHEMAS` trong `base.py`.
2. Schema mới sẽ tự được tạo bởi `migrate_schemas` (bước 1) — connection `schema_<tên>`
   cũng tự sinh từ vòng lặp trong `base.py`.
3. Chạy lại `python manage.py migrate_schemas`.

### Hạn chế đã cân nhắc

- **Không phải isolation bảo mật thật sự**: search_path chứa tất cả schema nên vẫn query chéo được.
  Muốn cô lập tuyệt đối phải bỏ FK chéo app (dùng id + join thủ công).
- **SQLite (dev) không hỗ trợ schema** — router tự fallback về connection `default` duy nhất.
- `django_migrations` được ghi trong schema đầu của mỗi connection (VD `user.django_migrations`),
  không nằm ở `public` — đừng tìm nhầm chỗ khi debug.

---

## Cấu Trúc Thư Mục Chi Tiết

### 1. `config/` — Cấu hình Django

```
config/
├── __init__.py
├── asgi.py              # ASGI config: HTTP + WebSocket (Channels)
├── wsgi.py              # WSGI config: Gunicorn
├── celery.py            # Celery app: async task processing
├── urls.py              # URL routing chính
└── settings/
    ├── __init__.py      # Auto-load settings theo DJANGO_ENV
    ├── base.py          # Settings chung cho mọi môi trường
    ├── development.py   # Dev: debug toolbar, CORS allow all
    ├── staging.py       # Staging: kế thừa production + debug
    └── production.py    # Production: SSL, Sentry, DB pool, security
```

**Chi tiết `config/settings/base.py`:**

| Cấu hình                | Mô tả                                                     |
| ----------------------- | --------------------------------------------------------- |
| `SECRET_KEY`            | Từ env `DJANGO_SECRET_KEY`                                |
| `DEBUG`                 | Từ env `DJANGO_DEBUG`                                     |
| `DATABASES`             | PostgreSQL mặc định, config qua env                       |
| `CACHES`                | Redis cache với connection pool                           |
| `CHANNEL_LAYERS`        | Redis cho WebSocket/Channels                              |
| `CELERY_*`              | Celery config (broker, serializer, beat)                  |
| `REST_FRAMEWORK`        | JWT auth, pagination, filtering, exception handler        |
| `PASSWORD_MAX_AGE_DAYS` | Số ngày hết hạn mật khẩu (mặc định 90 ngày)               |
| `OTP_*`                 | Cấu hình OTP cho quên/đặt lại mật khẩu                    |
| `CORS_*`                | CORS config, whitelist origins                            |
| `SPECTACULAR_SETTINGS`  | Swagger/ReDoc config                                      |
| `EMAIL_*`               | SMTP config                                               |
| `USE_PGVECTOR`          | Bật/tắt pgvector (mặc định True; SQLite dev tự đặt False) |
| `LOGGING`               | Console + Rotating file handler                           |

**Cách chọn môi trường:**

```bash
# Mặc định: development
python manage.py runserver

# Production
$env:DJANGO_ENV="production"
python manage.py runserver
```

---

### 2. `apps/` — Django Applications

```
apps/
├── __init__.py
├── core/              # BASE: BaseModel, BaseManager, BaseSerializer, BaseViewSet
├── accounts/          # AUTH: User model, JWT, register, login, logout, password policy
├── api/               # API: Routing v1, health check endpoints
├── face/              # FACE: Face recognition (InsightFace + pgvector)
├── info/              # INFO: Organization hierarchy, Header menu structure (3 cấp)
└── websocket/         # WS: Channels consumers
```

#### `apps/core/` — Core System

```python
# apps/core/models.py
class BaseModel(models.Model):
    """Abstract base model cho tất cả models trong hệ thống."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
```

**Lưu ý:** BaseModel KHÔNG có `is_active` và `is_deleted`. Dữ liệu được xóa trực tiếp (hard delete).

#### `apps/accounts/` — Authentication & Authorization

| Endpoint                                 | Method   | Mô tả                                     |
| ---------------------------------------- | -------- | ----------------------------------------- |
| `/api/v1/accounts/auth/register/`        | POST     | Đăng ký user mới                          |
| `/api/v1/accounts/auth/login/`           | POST     | JWT login                                 |
| `/api/v1/accounts/auth/refresh/`         | POST     | Refresh access token                      |
| `/api/v1/accounts/auth/logout/`          | POST     | Logout (blacklist token)                  |
| `/api/v1/accounts/auth/me/`              | GET/POST | Xem/cập nhật profile                      |
| `/api/v1/accounts/auth/change-password/` | POST     | Đổi mật khẩu (kiểm tra hết hạn 90 ngày)   |
| `/api/v1/accounts/auth/forgot-password/` | POST     | Quên mật khẩu — gửi OTP qua Redis + email |
| `/api/v1/accounts/auth/reset-password/`  | POST     | Đặt lại mật khẩu — xác minh OTP từ Redis  |

**User Model** (matching `_0010_user`):

```python
class User(models.Model):
    id = models.BigAutoField(primary_key=True)
    crt_at = models.DateTimeField(auto_now_add=True)
    upd_at = models.DateTimeField(auto_now=True)
    change_pw_at = models.DateTimeField(auto_now_add=True)

    org = models.ForeignKey(Organization, on_delete=models.PROTECT, db_column="org_id")
    shift = models.ForeignKey(Shift, on_delete=models.PROTECT, db_column="shift_id")

    gen_id = models.CharField(max_length=8, unique=True, db_index=True)   # 8 chữ số
    knox_id = models.CharField(max_length=15, unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=50)
    status = models.PositiveSmallIntegerField(choices=..., default=0)
    # 0 waiting / 1 approved / 2 reject / 3 block / 4 deleted
    ip_remember = models.CharField(max_length=15, null=True, blank=True)
    password = models.CharField(max_length=128)

    class Meta:
        db_table = "_0010_user"
```

Login qua **`gen_id`** (8 chữ số) hoặc **`knox_id`** (giống email, không có @).

#### `apps/info/` — Menu Hệ Thống (Header 3 cấp)

Header menu được render theo phân cấp 3 cấp: **Group → Pages → SystemHeader**.

```
GroupHeader (thanh tiêu đề)
└── PagesHeader (dropdown cấp 1 khi hover Group)
    └── SystemHeader (sub-dropdown cấp 2, là Header/View thực tế)
```

| Endpoint                          | Method | Mô tả                                           |
| --------------------------------- | ------ | ----------------------------------------------- |
| `/api/v1/info/headers/structure/` | GET    | Cây menu 3 cấp đầy đủ (Group → Pages → Headers) |
| `/api/v1/info/group-headers/`     | GET    | Danh sách GroupHeader                           |
| `/api/v1/info/page-headers/`      | GET    | Danh sách PagesHeader                           |
| `/api/v1/info/system-headers/`    | GET    | Danh sách SystemHeader                          |

Cấu trúc response của `/headers/structure/`:

```json
{
	"success": true,
	"data": [
		{
			"id": 1,
			"group_vi": "KCS",
			"group_en": "KCS",
			"group_kr": "KCS",
			"is_use": true,
			"pages": [
				{
					"id": 10,
					"page_vi": "Kiểm tra",
					"page_en": "Inspection",
					"page_kr": "검사",
					"is_use": true,
					"headers": [
						{
							"id": 100,
							"view_vi": "view_kcs_in",
							"view_en": "view_kcs_in",
							"view_kr": "view_kcs_in",
							"header_vi": "KCS Đầu vào",
							"header_en": "Incoming KCS",
							"header_kr": "입고 KCS",
							"sort": 1,
							"is_use": true,
							"is_mobile": false
						}
					]
				}
			]
		}
	]
}
```

#### `apps/face/` — Face Recognition

```
apps/face/
├── models.py               # FaceEmbedding (pgvector VectorField(512))
├── serializers.py          # FaceRegister/Search/Verify serializers
├── views.py                # FaceRegisterView, FaceSearchView, FaceVerifyView
├── migrations/0002_pgvector.py  # Migration có điều kiện: cài extension + convert cột
└── services/face_service.py     # InsightFace extract + tìm kiếm tương đồng
```

- **Model**: `FaceEmbedding.embedding` là cột `vector(512)` native của **pgvector** trên PostgreSQL. Trên backend khác (SQLite dev) tự fallback về cột JSON text.
- **Tìm kiếm**: trên PostgreSQL chạy cosine distance (`<=>`) ngay trong DB qua `face_service.find_best_match()`; backend khác fallback brute-force Python.
- **Môi trường**: bật/tắt bằng `USE_PGVECTOR`; migration `0002` là no-op khi tắt.

#### `apps/websocket/` — WebSocket

| Consumer               | Route                | Mô tả                   |
| ---------------------- | -------------------- | ----------------------- |
| `NotificationConsumer` | `ws/notifications/`  | Real-time notifications |
| `ChatConsumer`         | `ws/chat/<room_id>/` | Real-time chat          |

### 3. `services/` — Business Logic Layer

```
services/
├── __init__.py
├── base.py              # BaseService: CRUD operations
├── smtp_service.py      # EmailService: gửi email (SMTP, SendGrid, Mailgun, SES)
├── redis_service.py     # RedisService: cache, rate limit, OTP, pub/sub, lock
├── curl_service.py      # HTTPService: HTTP client (sync + async)
├── socket_service.py    # SocketService: WebSocket messaging
├── queue_service.py     # QueueService: Celery task dispatch
└── storage_service.py   # StorageService: file storage (local, S3, GCS, MinIO)
```

#### `services/redis_service.py` — RedisService (bao gồm OTP)

```python
class RedisService:
    # ---- Cache Operations ----
    get(key, default)                # Lấy từ cache
    set(key, value, timeout=300)     # Set cache
    delete(key)                      # Xóa cache
    set_many(data, timeout)          # Set nhiều key
    get_many(keys)                   # Lấy nhiều key
    delete_pattern(pattern)          # Xóa theo pattern

    # ---- OTP (Forgot / Reset Password) ----
    store_otp(identifier, otp, ttl)          # Lưu OTP (khóa theo knox_id / gen_id)
    verify_otp(identifier, otp)              # Xác minh OTP
    delete_otp(identifier)                   # Xóa OTP sau khi dùng

    # ---- Rate Limiting ----
    check_rate_limit(key, max_requests, window)

    # ---- Distributed Lock ----
    acquire_lock(lock_key, timeout)
    release_lock(lock_key)

    # ---- Pub/Sub ----
    publish(channel, message)
```

Luồng quên / đặt lại mật khẩu:

```
POST /auth/forgot-password/  { account }
        │  sinh OTP bằng secrets, lưu Redis otp:<knox_id|gen_id>, gửi email
        ▼
POST /auth/reset-password/   { account, otp, new_password }
        │  verify OTP từ Redis → đổi mật khẩu → xóa OTP
        ▼
     đăng nhập với mật khẩu mới
```

### 4. `libs/` — Shared Libraries

```
libs/
├── __init__.py
├── exceptions.py       # Custom exception handler + custom exceptions
├── responses.py        # Standard response format
├── pagination.py       # Standard pagination
├── auth/               # JWT authentication stack
│   ├── jwt_utils.py            # generate_tokens, decode_access_token, blacklist
│   ├── authentication.py       # DRF JWTAuthentication (401 chuẩn)
│   ├── jwt_middleware.py       # Channels JWT middleware cho WebSocket (async-safe)
│   ├── password.py             # Password hashing/verify helpers
│   ├── password_validation.py  # StrongPasswordValidator
│   ├── throttling.py           # AuthRateThrottle, ScopedRateThrottle
│   └── anonymous_user.py       # AnonymousUser (thay django.contrib.auth)
└── middlewares/
    ├── content_negotiation.py
    ├── encryption.py
    ├── language.py
    └── rate_limit.py
```

**JWT WebSocket auth (`libs/auth/jwt_middleware.py`):**

- Xác thực qua header `Authorization: Bearer <token>` hoặc `?token=<token>` trên query string.
- User query chạy trong `database_sync_to_async` — an toàn với async event loop.
- Token invalid/hết hạn → fallback `AnonymousUser` (consumer tự quyết định từ chối).

#### `libs/responses.py` — Response Format

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
success_response(data, message, status, meta)   # 200 Success
error_response(message, errors, status, meta)   # 400 Error
created_response(data, message)                 # 201 Created
no_content_response()                           # 204 No Content
```

---

## Danh Sách API

### Authentication

| Method | Endpoint                                 | Auth | Mô tả                           |
| ------ | ---------------------------------------- | ---- | ------------------------------- |
| POST   | `/api/v1/accounts/auth/register/`        | No   | Đăng ký                         |
| POST   | `/api/v1/accounts/auth/login/`           | No   | Đăng nhập                       |
| POST   | `/api/v1/accounts/auth/refresh/`         | No   | Refresh token                   |
| POST   | `/api/v1/accounts/auth/logout/`          | Yes  | Đăng xuất                       |
| GET    | `/api/v1/accounts/auth/me/`              | Yes  | Profile                         |
| POST   | `/api/v1/accounts/auth/me/`              | Yes  | Cập nhật profile                |
| POST   | `/api/v1/accounts/auth/change-password/` | Yes  | Đổi mật khẩu                    |
| POST   | `/api/v1/accounts/auth/forgot-password/` | No   | Quên mật khẩu (gửi OTP)         |
| POST   | `/api/v1/accounts/auth/reset-password/`  | No   | Đặt lại mật khẩu (xác minh OTP) |

### Info / Menu Hệ Thống

| Method | Endpoint                          | Auth | Mô tả                                    |
| ------ | --------------------------------- | ---- | ---------------------------------------- |
| GET    | `/api/v1/info/headers/structure/` | Yes  | Cây menu 3 cấp (Group → Pages → Headers) |
| GET    | `/api/v1/info/group-headers/`     | Yes  | Danh sách Group                          |
| GET    | `/api/v1/info/page-headers/`      | Yes  | Danh sách Pages                          |
| GET    | `/api/v1/info/system-headers/`    | Yes  | Danh sách Headers                        |

### Health Check

| Method | Endpoint                | Mô tả                     |
| ------ | ----------------------- | ------------------------- |
| GET    | `/api/v1/health/`       | Health check (DB + Redis) |
| GET    | `/api/v1/health/ready/` | Readiness probe           |
| GET    | `/api/v1/health/live/`  | Liveness probe            |

### API Documentation

| Method | Endpoint       | Mô tả                 |
| ------ | -------------- | --------------------- |
| GET    | `/api/docs/`   | Swagger UI            |
| GET    | `/api/redoc/`  | ReDoc                 |
| GET    | `/api/schema/` | OpenAPI Schema (JSON) |

### FaceID (Face Recognition)

| Method | Endpoint                 | Auth | Mô tả                                              |
| ------ | ------------------------ | ---- | -------------------------------------------------- |
| POST   | `/api/v1/face/register/` | Yes  | Đăng ký face embedding cho **chính user hiện tại** |
| POST   | `/api/v1/face/search/`   | Yes  | Tìm kiếm user giống nhất với ảnh face (1:N)        |
| POST   | `/api/v1/face/verify/`   | Yes  | Verify face khớp với user chỉ định (1:1)           |

**Lưu ý:**

- Dùng InsightFace (ArcFace) — 512-dim embedding
- Embedding lưu trong cột `vector(512)` **pgvector** trên PostgreSQL; ảnh gốc lưu vào `media/faces/`
- Cosine similarity threshold mặc định: 0.6 (client có thể truyền `threshold` cho search)
- Trên PostgreSQL, matching chạy trong DB (`<=>`); SQLite dev fallback brute-force Python
- **Bảo mật**: cả 3 endpoint đều yêu cầu JWT; register luôn gắn với `request.user` (chống IDOR)

---

## Chính Sách Mật Khẩu & Xác Thực

### `keyCheck` — Yêu cầu đổi mật khẩu

Mỗi user trả về trường `keyCheck` trong response login/me:

| Giá trị | Ý nghĩa                                                       |
| ------- | ------------------------------------------------------------- |
| `0`     | Không cần đổi mật khẩu                                        |
| `1`     | Bắt buộc đổi mật khẩu (quá `PASSWORD_MAX_AGE_DAYS` = 90 ngày) |

Quy tắc tính `keyCheck` trong `User.keyCheck`:

```python
@property
def keyCheck(self) -> int:
    if self.change_pw_at and (timezone.now() - self.change_pw_at) < timedelta(days=90):
        return 0
    return 1
```

### Luồng bắt buộc đổi mật khẩu

1. User đăng nhập → nhận `keyCheck = 1`
2. Frontend mở modal **bắt buộc** đổi mật khẩu (không thể đóng, không yêu cầu mật khẩu hiện tại)
3. Gọi `POST /auth/change-password/` chỉ với `new_password`
4. Backend cập nhật `change_pw_at = now()`, trả `keyCheck = 0`
5. Modal tự đóng, user vào hệ thống bình thường

> **Lưu ý:** Đăng nhập AD SSO (SAML qua bên thứ 3) sẽ được tích hợp sau — khi đó
> user SSO sẽ được loại khỏi chính sách bắt buộc đổi mật khẩu.

### Quên / Đặt lại mật khẩu (Redis OTP)

1. **`POST /forgot-password/`** với `{ "account": "<gen_id | knox_id>" }`
   - Sinh OTP an toàn bằng `secrets.randbelow` (không dùng `random`)
   - Lưu vào Redis: `otp:<knox_id|gen_id>` với TTL `OTP_EXPIRY_SECONDS` (mặc định 300s)
   - Gửi OTP qua email (SMTP)
   - Trả về `knox_id` và `keyCheck`
2. **`POST /reset-password/`** với `{ "account", "otp", "new_password" }`
   - Xác minh OTP từ Redis (đúng khóa `knox_id` hoặc `gen_id`)
   - Nếu đúng → cập nhật mật khẩu mới + `change_pw_at`, xóa OTP
   - Nếu sai/hết hạn → trả `400 Invalid or expired OTP`

### Mật khẩu mạnh

`StrongPasswordValidator` (`libs/auth/password_validation.py`) bắt buộc:

- Tối thiểu 8 ký tự
- Ít nhất 1 chữ hoa
- Ít nhất 1 chữ thường
- Ít nhất 1 chữ số
- Ít nhất 1 ký tự đặc biệt
