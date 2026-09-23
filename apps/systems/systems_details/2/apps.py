from django.apps import AppConfig


class Header2Config(AppConfig):
	# App riêng của header 2 — đăng ký vào INSTALLED_APPS khi cần models per-header
	# (label phải tường minh vì tên package "2" không phải identifier hợp lệ)
	default_auto_field = "django.db.models.BigAutoField"
	name = "apps.systems.systems_details.2"
	label = "systems_details_header_2"
	verbose_name = "Header 2 — Waiting for IQC"
