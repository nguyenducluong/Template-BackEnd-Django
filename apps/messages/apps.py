from django.apps import AppConfig


class MessagesConfig(AppConfig):
	"""Cau hinh app messages (chat room kin)."""

	default_auto_field = 'django.db.models.BigAutoField'
	name = 'apps.messages'
	label = 'chat'

