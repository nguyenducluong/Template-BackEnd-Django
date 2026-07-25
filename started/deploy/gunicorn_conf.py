"""IQCG - Gunicorn config (used with systemd or standalone).
Run: gunicorn config.wsgi:application -c started/deploy/gunicorn_conf.py
"""
import multiprocessing
import os

bind = "127.0.0.1:8000"
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"
timeout = 120
keepalive = 5

accesslog = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "gunicorn_access.log")
errorlog = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs", "gunicorn_error.log")
loglevel = "info"

max_requests = 1000          # recycle workers to guard against leaks
max_requests_jitter = 100
