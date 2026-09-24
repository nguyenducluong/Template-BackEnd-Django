from django.apps import AppConfig


class System10000Config(AppConfig):
	# App mẫu của header 10000 — KHÔNG đăng ký vào INSTALLED_APPS.
	# (label phải tường minh vì tên package "10000" không phải identifier hợp lệ)
	default_auto_field = 'django.db.models.BigAutoField'
	name = 'apps.systems.systems_details.10000'
	label = 'systems_details_header_10000'
	verbose_name = 'Header 10000 — Mẫu phát triển'
