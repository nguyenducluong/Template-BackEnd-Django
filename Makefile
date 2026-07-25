# Django API Server Makefile
# Usage: make <command>

# Variables
PYTHON = .venv/Scripts/python.exe
MANAGE = $(PYTHON) manage.py
APP_NAME = django_api

.PHONY: help install dev migrate migrations makemigrations shell test run \
	runserver celery worker beat docker-up docker-down lint format clean

help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make dev           - Install development dependencies"
	@echo "  make migrate       - Run database migrations"
	@echo "  make migrations    - Make migrations (app=app_name)"
	@echo "  make makemigrations - Alias for migrations"
	@echo "  make shell         - Open Django shell"
	@echo "  make test          - Run tests"
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

migrations:
	$(MANAGE) makemigrations $(app)

makemigrations:
	$(MANAGE) makemigrations $(app)

shell:
	$(MANAGE) shell_plus

test:
	pytest

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