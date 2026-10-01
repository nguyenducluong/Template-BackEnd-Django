"""IQCG - Gunicorn config (used with systemd or standalone).
Run: gunicorn config.wsgi:application -c started/deploy/gunicorn_conf.py
"""
import multiprocessing
import os

bind = "127.0.0.1:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))

# gthread (DA, khong phai sync): 1 request chat AI stream co the giu connection 30-300s.
# Worker `sync` chi xu ly 1 request tai 1 thoi diem => 1 user chat se CHAN ca server,
# user khac phai cho worker khong ban rong. gthread moi tao luong rieng cho tung request
# chat ma worker ngay lap tuc quay di nhan request khac.
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", 8))

# 120s qua ngan cho stream (Ollama co the suy nghi 30-300s, xem OLLAMA_TIMEOUT).
# Worker bi kill giua chung stream se lam mat ket noi cho TAT CA user dang online.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 600))
keepalive = 5

accesslog = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "gunicorn_access.log")
errorlog = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "gunicorn_error.log")
loglevel = "info"

max_requests = 1000          # recycle workers to guard against leaks
max_requests_jitter = 100
