from django.apps import AppConfig


class Header1Config(AppConfig):
	# App riêng của header 1 — đăng ký vào INSTALLED_APPS khi cần models per-header
	# (label phải tường minh vì tên package "1" không phải identifier hợp lệ)
	default_auto_field = "django.db.models.BigAutoField"
	name = "apps.systems.systems_details.1"
	label = "systems_details_header_1"
	verbose_name = "Header 1 — Waiting for IQC"
