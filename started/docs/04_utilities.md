# 4. Tiá»‡n Ã­ch váº­n hÃ nh khÃ¡c

## 4.1 Log rotation

Django Ä‘Ã£ cáº¥u hÃ¬nh `RotatingFileHandler` (10 MB Ã— 5 file) táº¡i `logs/django.log`
trong `config/settings/base.py`. Nginx/Gunicorn log nÃªn thÃªm logrotate:

```
# /etc/logrotate.d/iqcg
/opt/iqcg/logs/*.log {
    daily
    rotate 14
    compress
    missingok
    notifempty
}
```

## 4.2 Health check & monitoring

- `GET /api/v1/health/` â€” kiá»ƒm tra DB + tá»•ng quan há»‡ thá»‘ng (khÃ´ng cáº§n auth)
- Uptime monitor bÃªn ngoÃ i (UptimeRobot) ping `/api/v1/health/` má»—i 1â€“5 phÃºt
- Sentry (tÃ¹y chá»n): set `SENTRY_DSN` trong `.env` production â€” `production.py`
  tá»± khá»Ÿi táº¡o náº¿u `sentry-sdk` Ä‘Ã£ cÃ i

## 4.3 Rotate RSA key (mÃ£ hÃ³a API)

```powershell
powershell -File started\scripts\rotate_rsa_key.ps1
```

Quy trÃ¬nh an toÃ n: sinh cáº·p má»›i vÃ o `certs/next/` â†’ deploy â†’ client handshake
láº¡i â†’ Ä‘á»•i `next/` thÃ nh key chÃ­nh thá»©c. Session cÅ© tá»± háº¿t háº¡n trong tá»‘i Ä‘a
`CRYPTO_SESSION_TTL` giÃ¢y.

## 4.4 Seed dá»¯ liá»‡u máº«u

```bash
python manage.py seed_data            # idempotent (update_or_create)
python manage.py seed_data --clean    # xÃ³a háº¿t rá»“i seed láº¡i
```

## 4.5 Celery worker / beat

```bash
celery -A config worker -l info       # worker
celery -A config beat -l info         # scheduler (task Ä‘á»‹nh ká»³)
```

Windows dev: cháº¡y kÃ¨m `--pool=solo`.

## 4.6 Dá»‹ch vÄƒn báº£n (i18n vi/en/kr)

```bash
django-admin makemessages -l vi -l kr
django-admin compilemessages
```

## 4.7 Database schema

Má»i model map vÃ o schema `system` (xem `DB_SCHEMAS` trong `base.py`,
router `libs/db_routers.py`). Khi cáº§n schema riÃªng cho app má»›i:
thÃªm entry vÃ o `DB_SCHEMAS` vÃ  táº¡o schema trong PostgreSQL:

```sql
CREATE SCHEMA IF NOT EXISTS system;
```
