from django.apps import AppConfig


class SystemDetailsConfig(AppConfig):
	default_auto_field = "django.db.models.BigAutoField"
	name = "apps.systems.systems_details"
	label = "systems_details"
	verbose_name = "Systems Details (dữ liệu view chi tiết theo header)"
