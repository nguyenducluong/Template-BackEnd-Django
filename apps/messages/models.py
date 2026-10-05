"""Models chat room kin (app messages).

Quy tac room kin:
- KHONG co chuc nang join: vao room chi bang add_member tu member hien tai.
- Bi kick / roi / giai tan -> mat quyen doc lich su.
- Owner roi nhom: bat buoc chon transfer_to hoac dissolve.
"""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class Conversation(models.Model):
	"""Phong chat: direct (1-1) hoac group (nhom kin)."""

	TYPE_DIRECT = 'direct'
	TYPE_GROUP = 'group'
	TYPE_CHOICES = [(TYPE_DIRECT, _('Direct')), (TYPE_GROUP, _('Group'))]

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TYPE_GROUP, db_index=True)
	name_global = models.CharField(max_length=200, blank=True, default='')
	avatar_url = models.CharField(max_length=500, blank=True, default='')
	created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='created_conversations')
	is_dissolved = models.BooleanField(default=False, db_index=True)
	dissolved_at = models.DateTimeField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		db_table = 'messages_conversation'
		ordering = ['-updated_at']

	def __str__(self):
		return self.name_global or str(self.id)


class ConversationMember(models.Model):
	"""Thanh vien room. Chi member moi add duoc user khac vao."""

	ROLE_OWNER = 'owner'
	ROLE_ADMIN = 'admin'
	ROLE_MEMBER = 'member'
	ROLE_CHOICES = [(ROLE_OWNER, _('Owner')), (ROLE_ADMIN, _('Admin')), (ROLE_MEMBER, _('Member'))]

	conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='members')
	user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='conversation_memberships')
	role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_MEMBER, db_index=True)
	joined_at = models.DateTimeField(auto_now_add=True)
	muted = models.BooleanField(default=False)
	# Đánh dấu yêu thích — RIÊNG TỪNG USER (giống Messenger): cùng 1 room có thể
	# người A ghim, người B không. Vì vậy field nằm ở membership chứ không nằm ở
	# Conversation.
	is_favorite = models.BooleanField(default=False, db_index=True)
	last_read_message = models.ForeignKey('Message', on_delete=models.SET_NULL, null=True, blank=True, related_name='last_read_by')

	class Meta:
		db_table = 'messages_conversation_member'
		constraints = [models.UniqueConstraint(fields=['conversation', 'user'], name='uniq_member_per_conversation_user')]

	def __str__(self):
		return f'{self.user_id}@{self.conversation_id} ({self.role})'


class ConversationAlias(models.Model):
	"""Ten rieng tung user dat cho nhom (khong anh huong nguoi khac)."""

	conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='aliases')
	user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='conversation_aliases')
	custom_name = models.CharField(max_length=200, blank=True, default='')

	class Meta:
		db_table = 'messages_conversation_alias'
		constraints = [models.UniqueConstraint(fields=['conversation', 'user'], name='uniq_alias_per_user_conversation')]


class Message(models.Model):
	"""Tin nhan trong room kin."""

	KIND_TEXT = 'text'
	KIND_MARKDOWN = 'markdown'
	KIND_TABLE = 'table'
	KIND_IMAGE = 'image'
	KIND_FILE = 'file'
	KIND_AUDIO = 'audio'
	KIND_SYSTEM = 'system'
	KIND_CHOICES = [
		(KIND_TEXT, _('Text')),
		(KIND_MARKDOWN, _('Markdown')),
		(KIND_TABLE, _('Table')),
		(KIND_IMAGE, _('Image')),
		(KIND_FILE, _('File')),
		(KIND_AUDIO, _('Audio')),
		(KIND_SYSTEM, _('System')),
	]

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
	sender = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='sent_messages')
	kind = models.CharField(max_length=16, choices=KIND_CHOICES, default=KIND_TEXT, db_index=True)
	body = models.TextField(blank=True, default='')
	table_data = models.JSONField(null=True, blank=True)
	file_url = models.CharField(max_length=500, blank=True, default='')
	file_name = models.CharField(max_length=255, blank=True, default='')
	file_size = models.BigIntegerField(default=0)
	mime = models.CharField(max_length=128, blank=True, default='')
	reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
	forward_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='forwards')
	is_edited = models.BooleanField(default=False)
	is_deleted = models.BooleanField(default=False, db_index=True)
	created_at = models.DateTimeField(auto_now_add=True, db_index=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		db_table = 'messages_message'
		ordering = ['created_at']
		indexes = [models.Index(fields=['conversation', 'created_at'])]


class MessageRead(models.Model):
	"""Danh dau da doc (hien Seen)."""

	message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reads')
	user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='message_reads')
	read_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		db_table = 'messages_message_read'
		constraints = [models.UniqueConstraint(fields=['message', 'user'], name='uniq_read_per_message_user')]


class MessageReaction(models.Model):
	"""Tha icon cho tin nhan (kieu Messenger)."""

	message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
	user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='message_reactions')
	emoji = models.CharField(max_length=16)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		db_table = 'messages_message_reaction'
		constraints = [models.UniqueConstraint(fields=['message', 'user', 'emoji'], name='uniq_reaction_per_user_emoji')]