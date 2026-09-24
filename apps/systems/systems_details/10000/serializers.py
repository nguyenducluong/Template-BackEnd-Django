"""
Serializers của Header 10000 — validate request view chi tiết demo.

header_id KHÔNG có trong body: đã biết từ URL (/api/v1/systems/details/10000).
Demo không cần DB/quyền — validate hình thức như header thật.
"""

from rest_framework import serializers


class DetailsQuerySerializer(serializers.Serializer):
	"""Tham số nghiệp vụ của view chi tiết — khớp query frontend giữ trong Redux."""

	org = serializers.ListField(child=serializers.CharField(), required=False, default=list)
	period = serializers.DictField(child=serializers.JSONField(), required=False, default=dict)
	details = serializers.DictField(child=serializers.JSONField(), required=False, default=dict)
	limit = serializers.IntegerField(required=False, min_value=1, default=50)
	offset = serializers.IntegerField(required=False, min_value=0, default=0)


class Header10000DetailsRequestSerializer(serializers.Serializer):
	"""Body của POST /api/v1/systems/details/10000."""

	scope = serializers.ChoiceField(
		choices=['full', 'data'],
		default='data',
		help_text="full: lần đầu mở header (config+initial_state+data); data: chỉ dữ liệu search.",
	)
	query = DetailsQuerySerializer(required=False)

	def validate(self, attrs):
		attrs.setdefault('query', {})
		return attrs
