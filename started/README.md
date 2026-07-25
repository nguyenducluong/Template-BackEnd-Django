# started/

Tài liệu vận hành & script triển khai cho dự án Django API (IQCG).

## Mục lục

| File | Nội dung |
|---|---|
| [docs/01_encryption_guide.md](docs/01_encryption_guide.md) | Mã hóa API 2 chiều (RSA handshake + AES-GCM) — hướng dẫn Client & Server |
| [docs/02_production_deploy.md](docs/02_production_deploy.md) | Deploy Production (Gunicorn + Nginx + systemd) |
| [docs/05_deploy_xampp.md](docs/05_deploy_xampp.md) | Deploy trên XAMPP (Windows + Apache) |
| [docs/03_postgres_backup.md](docs/03_postgres_backup.md) | Backup PostgreSQL hàng ngày/giờ + restore |
| [docs/04_utilities.md](docs/04_utilities.md) | Tiện ích: log rotation, health check, rotate key, seed... |

## Thư mục

```
docs/      Tài liệu hướng dẫn
scripts/   backup_db.ps1 / backup_db.sh / gen_server_keys.ps1 / rotate_rsa_key.ps1
deploy/    nginx.conf, httpd-django.conf, iqcg.service, gunicorn_conf.py,
           env.production.example
```

## Quick start

```powershell
# 1. Tạo server keys (lần đầu)
powershell -File scripts\gen_server_keys.ps1

# 2. Migrate + seed
python manage.py migrate
python manage.py seed_data

# 3. Chạy dev server (mã hóa tự TẮT khi DJANGO_ENV=development)
python manage.py runserver
```
