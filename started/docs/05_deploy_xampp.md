# 5. Deploy trên XAMPP (Windows + Apache)

Kiến trúc khuyến nghị: **Apache (XAMPP) làm reverse proxy → Waitress/Django
chạy ở localhost:8000**. Ổn định hơn mod_wsgi và hỗ trợ tốt WebSocket.

## 5.1 Chạy Django app

```powershell
cd E:\VsCode\django
.venv\Scripts\activate
set DJANGO_ENV=production
python manage.py migrate
python manage.py collectstatic --noinput

# App server (chọn 1)
pip install waitress
waitress-serve --host=127.0.0.1 --port=8000 config.wsgi:application

# WebSocket (nếu dùng Channels)
daphne -b 127.0.0.1 -p 8001 config.asgi:application
```

Chạy nền vĩnh viễn bằng **NSSM** (khuyến nghị):

```powershell
nssm install IQCG-Django "E:\VsCode\django\.venv\Scripts\waitress-serve.exe" "--host=127.0.0.1 --port=8000 config.wsgi:application"
nssm set IQCG-Django AppDirectory E:\VsCode\django
nssm set IQCG-Django AppEnvironment DJANGO_ENV=production
nssm start IQCG-Django
```

## 5.2 Cấu hình Apache (XAMPP)

Bật module proxy trong `C:\xampp\apache\conf\httpd.conf` (bỏ comment):

```apache
LoadModule proxy_module modules/mod_proxy.so
LoadModule proxy_http_module modules/mod_proxy_http.so
LoadModule proxy_wstunnel_module modules/mod_proxy_wstunnel.so
LoadModule rewrite_module modules/mod_rewrite.so
LoadModule headers_module modules/mod_headers.so
LoadModule ssl_module modules/mod_ssl.so
```

Include vhost — thêm vào cuối `httpd.conf`:

```apache
Include conf/extra/httpd-django.conf
```

Copy `started/deploy/httpd-django.conf` vào
`C:\xampp\apache\conf\extra\httpd-django.conf` rồi restart Apache từ
XAMPP Control Panel.

Nội dung file (tóm tắt — bản đầy đủ trong `deploy/httpd-django.conf`):

```apache
<VirtualHost *:80>
    ServerName iqcg.local
    ProxyPreserveHost On
    ProxyPass        /static/ !
    ProxyPass        /media/  !
    ProxyPass        /ws/     ws://127.0.0.1:8001/ws/
    ProxyPass        /        http://127.0.0.1:8000/
    ProxyPassReverse /        http://127.0.0.1:8000/
    Alias /static/  "E:/VsCode/django/staticfiles/"
    Alias /media/   "E:/VsCode/django/media/"
    <Directory "E:/VsCode/django/staticfiles"> Require all granted </Directory>
</VirtualHost>
```

HTTPS: cấu hình SSL trong `C:\xampp\apache\conf\extra\httpd-ssl.conf`
(XAMPP có sẵn self-signed cert; đổi sang cert thật nếu có domain).

## 5.3 DNS local (test)

Thêm vào `C:\Windows\System32\drivers\etc\hosts`:

```
127.0.0.1    iqcg.local
```

## 5.4 Checklist

- [ ] `DJANGO_ENV=production` (mã hóa API tự bật) — set qua NSSM env hoặc `SetEnv` trong vhost
- [ ] PostgreSQL + Redis đang chạy như service Windows
- [ ] `certs/` tồn tại (`scripts\gen_server_keys.ps1`)
- [ ] Backup Task Scheduler đã tạo (xem `03_postgres_backup.md`)
- [ ] Chỉ mở port 80/443 trên firewall; 5432/6379 không public
