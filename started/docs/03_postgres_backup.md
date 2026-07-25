# 3. Backup PostgreSQL hàng ngày / hàng giờ

## 3.1 Cấu hình

Cả hai script đều dùng biến môi trường (đọc từ `.env` dự án):
`DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

Thư mục backup mặc định: `E:\Backups\iqcg` (Windows) / `/var/backups/iqcg` (Linux).

## 3.2 Windows (XAMPP server)

```powershell
# Chạy thủ công
powershell -ExecutionPolicy Bypass -File started\scripts\backup_db.ps1 -Frequency daily
powershell -ExecutionPolicy Bypass -File started\scripts\backup_db.ps1 -Frequency hourly

# Lên lịch Task Scheduler (hàng ngày 02:00)
schtasks /create /tn "IQCG DB Backup Daily" /tr "powershell -ExecutionPolicy Bypass -File E:\VsCode\django\started\scripts\backup_db.ps1 -Frequency daily" /sc daily /st 02:00 /ru SYSTEM

# Lên lịch hàng giờ
schtasks /create /tn "IQCG DB Backup Hourly" /tr "powershell -ExecutionPolicy Bypass -File E:\VsCode\django\started\scripts\backup_db.ps1 -Frequency hourly" /sc hourly /ru SYSTEM
```

Retention mặc định: daily 30 file, hourly 48 file (tự xóa file cũ).

## 3.3 Linux (cron)

```bash
chmod +x started/scripts/backup_db.sh
crontab -e
# Hàng ngày 02:00
0 2 * * * /opt/iqcg/started/scripts/backup_db.sh daily >> /var/log/iqcg-backup.log 2>&1
# Hàng giờ
0 * * * * /opt/iqcg/started/scripts/backup_db.sh hourly >> /var/log/iqcg-backup.log 2>&1
```

## 3.4 Restore

```bash
# Giải nén và restore (xác nhận trước khi drop!)
pg_restore -h localhost -U postgres -d iqcg --clean --if-exists iqcg_2026-08-30_0200.dump
```

> Script tạo file `.dump` (custom format, nén) — khuyến nghị hơn plain SQL
> vì có thể restore chọn lọc (`--table`) và song song (`-j 4`).

## 3.5 Khuyến nghị thêm

- Copy bản backup hàng ngày sang ổ/network drive khác (3-2-1 rule)
- Test restore **định kỳ hàng tháng** vào DB tạm
- Với VPS nhỏ: backup + rsync sang storage ngoài qua cron đêm
