"""Serializers cho app messages (chat room kin)."""

from rest_framework import serializers

from .models import Conversation, ConversationMember, Message, MessageReaction


class MessageReactionSerializer(serializers.ModelSerializer):
	"""1 reaction cua 1 user tren tin nhan."""

	class Meta:
		model = MessageReaction
		fields = ['emoji', 'user_id', 'created_at']
		read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
	"""Thong tin room + ten hien thi (uu tien alias cua chinh user)."""

	display_name = serializers.SerializerMethodField()
	member_count = serializers.SerializerMethodField()
	last_message = serializers.SerializerMethodField()
	unread_count = serializers.SerializerMethodField()
	is_favorite = serializers.SerializerMethodField()
	my_alias = serializers.SerializerMethodField()

	class Meta:
		model = Conversation
		fields = ['id', 'type', 'name_global', 'display_name', 'avatar_url', 'is_dissolved', 'member_count', 'last_message', 'unread_count', 'is_favorite', 'my_alias', 'created_at', 'updated_at']
		read_only_fields = fields

	def get_my_alias(self, obj):
		"""Ten rieng user dat cho room nay (de GroupInfoPanel khoi tao dung gia tri)."""
		return (self.context or {}).get('aliases', {}).get(str(obj.id)) or ''

	def get_display_name(self, obj):
		alias = (self.context or {}).get('aliases', {}).get(str(obj.id))
		if alias:
			return alias
		if obj.type == Conversation.TYPE_DIRECT:
			partner = (self.context or {}).get('partners', {}).get(str(obj.id))
			if partner:
				return partner
		return obj.name_global or str(obj.id)

	def get_member_count(self, obj):
		counts = (self.context or {}).get('member_counts', {})
		return counts.get(str(obj.id), 0)

	def get_last_message(self, obj):
		"""Tin nhan cuoi cua room — nguon cho preview trong danh sach hoi thoai.

		`context['last_messages']` do `dispatch_conversations.build_context` gom
		sap. Khong co du lieu thi tra None (UI hien "Chua co tin nhan").

		PHẢI truyền lại `self.context`: bản cũ gọi `MessageSerializer(payload)`
		không context ⇒ mất `viewer_id` ⇒ cờ `mine` của reaction luôn False, và
		`get_reactions` rơi về nhánh query lẻ cho từng tin (N+1).
		"""
		payload = (self.context or {}).get('last_messages', {}).get(str(obj.id))
		return MessageSerializer(payload, context=self.context).data if payload is not None else None

	def get_unread_count(self, obj):
		"""So tin chua doc cua CHINH user nay (server la nguon su that).

		Doc tu context de tranh 1 query moi moi phong.
		"""
		counts = (self.context or {}).get('unread_counts', {})
		return counts.get(str(obj.id), 0)

	def get_is_favorite(self, obj):
		return (self.context or {}).get('favorites', {}).get(str(obj.id), False)


class ConversationMemberSerializer(serializers.ModelSerializer):
	"""Thanh vien room kem ten hien thi."""

	full_name = serializers.CharField(source='user.full_name', read_only=True)
	gen_id = serializers.CharField(source='user.gen_id', read_only=True)

	class Meta:
		model = ConversationMember
		fields = ['id', 'user_id', 'full_name', 'gen_id', 'role', 'muted', 'joined_at']
		read_only_fields = fields


class MessageSerializer(serializers.ModelSerializer):
	"""Tin nhan (an body khi bi xoa mem)."""

	sender_name = serializers.CharField(source='sender.full_name', read_only=True, default='')
	# gen_id của người gửi — DỰ PHÒNG cho FE khi `auth.user_info.id` chưa có
	# (ví dụ phiên được khôi phục từ token mà chưa kịp nạp lại hồ sơ user).
	sender_gen_id = serializers.CharField(source='sender.gen_id', read_only=True, default='')
	reactions = serializers.SerializerMethodField()

	# BẮT BUỘC ép 3 khoá UUID về STRING thủ công.
	#
	# LÝ DO (lỗi socket đứt khi gửi tin): với khoá ngoại, DRF dùng
	# `PrimaryKeyRelatedField` mà `to_representation` trả về `value.pk` — tức là
	# đối tượng `uuid.UUID`, KHÔNG phải chuỗi. REST còn che được vì JSONRenderer
	# của DRF tự ép UUID thành string, nhưng khi payload đi qua channel layer
	# (channels_redis) thì JSON serializer của nó ném
	# `TypeError: can not serialize 'UUID' object` ⇒ consumer chết ⇒ socket của
	# người gửi bị ngắt ngay sau khi gửi tin.
	# `conversation_id` / `reply_to_id` / `forward_from_id` là ATTNAME của khoá
	# ngoại; khai báo tường minh bằng CharField để giá trị trả về là CHUỖI.
	conversation = serializers.CharField(source='conversation_id', read_only=True)
	reply_to_id = serializers.CharField(read_only=True, allow_null=True)
	forward_from_id = serializers.CharField(read_only=True, allow_null=True)

	class Meta:
		model = Message
		fields = [
			'id', 'conversation', 'sender_id', 'sender_name', 'sender_gen_id', 'kind', 'body', 'table_data',
			'file_url', 'file_name', 'file_size', 'mime', 'reply_to_id', 'forward_from_id',
			'is_edited', 'is_deleted', 'reactions', 'created_at', 'updated_at',
		]
		read_only_fields = fields

	def get_reactions(self, instance):
		"""Reactions cua tin nhan, kem co `mine` cho user dang xem.

		NGUON SU THAT DUY NHAT cho UI reaction: FE KHONG con state reaction rieng
		⇒ reload / doi phong / mo lai van thay dung, va ca nguoi gui + nguoi nhan
		luon thay giong nhau.

		Doc tu context (`reactions_map`) de tranh N+1 khi serialize ca trang lich su.
		"""
		viewer_id = (self.context or {}).get('viewer_id')
		rows = (self.context or {}).get('reactions_map', {}).get(str(instance.id))
		if rows is None:
			# KHÔNG dùng `.only()` / `.select_related()` ở đây: cả hai đều tạo
			# queryset MỚI nên bỏ qua prefetch cache ⇒ mỗi tin lại bắn 1 query
			# (N+1). `.all()` mới dùng được cache đã `prefetch_related`.
			# `user_id` nằm ngay trên bảng reaction nên không cần join sang user.
			rows = list(instance.reactions.all())
		return [{'emoji': row.emoji, 'user_id': row.user_id, 'mine': str(row.user_id) == str(viewer_id)} for row in rows]

	def to_representation(self, instance):
		data = super().to_representation(instance)
		if instance.is_deleted:
			data['body'] = ''
			data['table_data'] = None
			data['file_url'] = ''
			data['file_name'] = ''
			data['reactions'] = []
		return data


class DispatchSerializer(serializers.Serializer):
	"""Payload dispatcher POST /api/v1/messages/dispatch {resource, action, id, data, params}."""

	resource = serializers.CharField()
	action = serializers.CharField()
	id = serializers.CharField(required=False, allow_null=True, default=None)
	data = serializers.DictField(required=False, default=dict)
	params = serializers.DictField(required=False, default=dict)
