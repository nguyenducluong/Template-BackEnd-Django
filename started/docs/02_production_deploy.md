# 2. Deploy Production (Linux: Gunicorn + Nginx + systemd)

## 2.1 Chuẩn bị

```bash
sudo apt update && sudo apt install -y python3-venv nginx postgresql redis-server
git clone <repo> /opt/iqcg && cd /opt/iqcg
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements/base.txt -r requirements/prod.txt
cp started/deploy/env.production.example /opt/iqcg/.env   # điền giá trị thật
```

Tạo server keys (xem `01_encryption_guide.md` §1.1) vào `/opt/iqcg/certs/`.

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

## 2.2 Gunicorn (WSGI + worker ASGI cho Channels)

```bash
gunicorn config.wsgi:application -c started/deploy/gunicorn_conf.py
```

`gunicorn_conf.py` đã cấu hình sẵn: bind `127.0.0.1:8000`, 4 workers,
access log vào `logs/gunicorn.log`. WebSocket chạy qua Daphne/Uvicorn:

```bash
daphne -b 127.0.0.1 -p 8001 config.asgi:application
```

## 2.3 systemd

```bash
sudo cp started/deploy/iqcg.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now iqcg
sudo systemctl status iqcg
```

## 2.4 Nginx

```bash
sudo cp started/deploy/nginx.conf /etc/nginx/sites-available/iqcg
sudo ln -s /etc/nginx/sites-available/iqcg /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Cấu hình gồm: HTTPS (certbot), proxy `/` → gunicorn 8000, proxy WS
`/ws/` → daphne 8001, serve `/static/` `/media/` trực tiếp.

## 2.5 Checklist go-live

- [ ] `.env`: `DJANGO_ENV=production`, `DJANGO_DEBUG=False`, secret key riêng
- [ ] Firewall chỉ mở 80/443; PostgreSQL/Redis không lặp ra ngoài
- [ ] `certs/` permission 600, **không** commit git (đã gitignore)
- [ ] Cron backup DB (xem `03_postgres_backup.md`)
- [ ] HTTPS cert hợp lệ (`certbot --nginx`)
- [ ] Test login E2E qua domain thật
