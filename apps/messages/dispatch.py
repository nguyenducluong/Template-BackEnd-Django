"""Dispatcher app messages: POST /api/v1/messages/dispatch {resource, action, id, data, params}."""

from django.utils.translation import gettext as _

from rest_framework import status

from libs.responses import error_response

from . import dispatch_conversations, dispatch_members, dispatch_messages, dispatch_reactions, dispatch_room, dispatch_upload

RESOURCES = ('conversations', 'members', 'messages', 'reactions', 'attachments')


def handle(resource, action, user, item_id=None, data=None, params=None, language='vi', request=None):
	"""Chay 1 action cua dispatcher - LUON tra envelope (khong raise).

	`request` chi can cho action upload (doc multipart tren request.FILES).
	"""
	data = data if isinstance(data, dict) else {}
	params = params if isinstance(params, dict) else {}
	if resource == 'conversations':
		if action in ('list', 'retrieve', 'create_direct', 'create_group'):
			calls = {
				'list': lambda: dispatch_conversations.handle_list(user),
				'retrieve': lambda: dispatch_conversations.handle_retrieve(user, item_id),
				'create_direct': lambda: dispatch_conversations.handle_create_direct(user, data),
				'create_group': lambda: dispatch_conversations.handle_create_group(user, data),
			}
			return calls[action]()
		if action in ('rename_global', 'set_avatar', 'set_alias', 'set_favorite', 'leave'):
			return dispatch_room.handle_single(action, user, item_id, data)
	if resource == 'members':
		return dispatch_members.handle_members(action, user, item_id, data)
	if resource == 'messages':
		return dispatch_messages.handle_messages(action, user, item_id, data, params)
	if resource == 'reactions':
		return dispatch_reactions.handle_reactions(action, user, item_id, data)
	if resource == 'attachments':
		return dispatch_upload.handle_upload(action, user, item_id, data, params, request)
	return error_response(message=_('Unknown resource.'), status=status.HTTP_400_BAD_REQUEST)

