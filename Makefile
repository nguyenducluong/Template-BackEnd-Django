# Django API Server Makefile
# Usage: make <command>

# Variables
PYTHON = .venv/Scripts/python.exe
MANAGE = $(PYTHON) manage.py
APP_NAME = django_api

.PHONY: help install dev migrate migrate-all ensure-schemas migrations makemigrations shell test run \
	runserver celery worker beat docker-up docker-down lint format clean

help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make dev           - Install development dependencies"
	@echo "  make migrate       - Run database migrations (default connection)"
	@echo "  make migrate-all   - Migrate ALL schema connections (info -> user -> face -> default)"
	@echo "  make ensure-schemas - Create PostgreSQL schemas + pinned django_migrations"
	@echo "  make migrations    - Make migrations (app=app_name)"
	@echo "  make makemigrations - Alias for migrations"
	@echo "  make shell         - Open Django shell"
	@echo "  make test          - Run tests"
	@echo "  make schema        - Xuất OpenAPI schema (schema.yaml) + validate"
	@echo "  make run           - Run development server"
	@echo "  make celery        - Run Celery worker"
	@echo "  make beat          - Run Celery beat"
	@echo "  make docker-up     - Start Docker services"
	@echo "  make docker-down   - Stop Docker services"
	@echo "  make lint          - Run linters"
	@echo "  make format        - Format code"

install:
	pip install -r requirements/base.txt

dev:
	pip install -r requirements/dev.txt

migrate:
	$(MANAGE) migrate

# Thu tu migrate QUAN TRONG voi FK cheo schema:
#   schema_info truoc (tao organizations/shifts...), sau do schema_user
#   (FK user->org resolve qua search_path), roi schema_face_id (FK -> user).
# Vi du: neu schema_user chay truoc khi info ton tai, accounts.0002 se loi
#   ProgrammingError: relation "_0000_organizations" does not exist.
ensure-schemas:
	$(MANAGE) ensure_schemas

migrate-all: ensure-schemas
	$(MANAGE) migrate --database=schema_info
	$(MANAGE) migrate --database=schema_user
	$(MANAGE) migrate --database=schema_face_id
	$(MANAGE) migrate

migrations:
	$(MANAGE) makemigrations $(app)

makemigrations:
	$(MANAGE) makemigrations $(app)

shell:
	$(MANAGE) shell_plus

test:
	pytest

# Xuất OpenAPI schema (Swagger) để kiểm tra tài liệu API.
# BẮT BUỘC dùng -X utf8: schema có ký tự tiếng Việt/Hàn, console Windows mặc
# định cp1252 sẽ crash (UnicodeEncodeError) khi in schema ra stdout.
schema:
	$(PYTHON) -X utf8 $(MANAGE) spectacular --file schema.yaml --validate
	@echo "OpenAPI schema -> schema.yaml"

run:
	$(MANAGE) runserver 0.0.0.0:8000

celery:
	celery -A config.celery worker --loglevel=info

beat:
	celery -A config.celery beat --loglevel=info

docker-up:
	docker-compose -f docker/docker-compose.yml up -d

docker-down:
	docker-compose -f docker/docker-compose.yml down

lint:
	flake8 .
	black --check .
	isort --check-only .

format:
	black .
	isort .

collectstatic:
	$(MANAGE) collectstatic --noinput

createsuperuser:
	$(MANAGE) createsuperuser