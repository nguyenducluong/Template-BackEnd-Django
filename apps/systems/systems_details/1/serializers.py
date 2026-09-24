"""
Serializers riêng của Header 1 — validate request view chi tiết.

header_id KHÔNG có trong body: đã biết từ URL (/api/v1/systems/details/1).
"""

from rest_framework import serializers


class DetailsQuerySerializer(serializers.Serializer):
	"""Tham số nghiệp vụ của view chi tiết — khớp query frontend giữ trong Redux."""

	org = serializers.ListField(child=serializers.CharField(), required=False, default=list)
	period = serializers.DictField(child=serializers.JSONField(), required=False, default=dict)
	details = serializers.DictField(child=serializers.JSONField(), required=False, default=dict)
	limit = serializers.IntegerField(required=False, min_value=1, default=50)
	offset = serializers.IntegerField(required=False, min_value=0, default=0)


class Header1DetailsRequestSerializer(serializers.Serializer):
	"""Body của POST /api/v1/systems/details/1."""

	scope = serializers.ChoiceField(
		choices=["full", "data"],
		default="data",
		help_text="full: lần đầu mở header (config+initial_state+data); data: chỉ dữ liệu search.",
	)
	query = DetailsQuerySerializer(required=False)

	def validate(self, attrs):
		attrs.setdefault("query", {})
		return attrs


class SubmitFormFileSerializer(serializers.Serializer):
	"""1 entry trong params.files — metadata FE gửi, server map với request.FILES."""

	__file_index = serializers.IntegerField(required=False)
	name = serializers.CharField(required=False, allow_blank=True, default="")
	size = serializers.IntegerField(required=False, default=0)
	mime = serializers.CharField(required=False, allow_blank=True, default="")


class SubmitFormSerializer(serializers.Serializer):
	"""Body params của func submit_form (dialog SUBMIT_FORM qua dispatcher).

	Validate hình thức (kiểu dữ liệu); validate nghiệp vụ (dialog/action thuộc
	header, field bắt buộc, power_key, dung lượng file) nằm ở base_system.
	"""

	header_id = serializers.IntegerField(required=False)
	dialog_id = serializers.CharField(required=False, allow_blank=True, default="")
	action_id = serializers.CharField(required=False, allow_blank=True, default="")
	power_key = serializers.IntegerField(required=False, allow_null=True, default=None)
	record_id = serializers.JSONField(required=False, allow_null=True, default=None)
	values = serializers.DictField(child=serializers.JSONField(), required=False, default=dict)
	files = SubmitFormFileSerializer(many=True, required=False, default=list)
	query = serializers.DictField(child=serializers.JSONField(), required=False, default=dict)
	request_id = serializers.CharField(required=False, allow_blank=True, default="")
