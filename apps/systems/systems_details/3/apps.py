from django.apps import AppConfig


class Header2Config(AppConfig):
	# App riêng của header 3 — đăng ký vào INSTALLED_APPS khi cần models per-header
	# (label phải tường minh vì tên package "3" không phải identifier hợp lệ)
	default_auto_field = "django.db.models.BigAutoField"
	name = "apps.systems.systems_details.3"
	label = "systems_details_header_3"
	verbose_name = "Header 3 — Waiting for IQC"
