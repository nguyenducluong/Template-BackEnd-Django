"""
Header 10000 — Demo (KHÔNG dùng production, KHÔNG cần DB/quyền).

- Func handlers cho dispatcher ``init_data`` — override từ base_system để
  minh hoạ 1 pattern/func. Header thật (1, 2, ...) làm theo các TODO dưới.
- Header10000DetailsView: endpoint test riêng — POST /api/v1/systems/details/10000
  (KHÔNG đăng ký vào urls cha nên không bao giờ lọt production).
  Bypass quyền demo: dùng header demo tại chỗ, không get_object_or_404 DB.
"""

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.info.models import SystemHeader
from apps.info.permissions import HasHeaderPermission
from apps.systems.systems_details import base_system
from apps.systems.systems_details.base_system import (  # noqa: F401
	action,
	dashboard,
	definition,
	details,
	download,
	search,
	submit_form,
)
from .serializers import Header10000DetailsRequestSerializer
from libs.auth.throttling import ScopedRateThrottle
from libs.responses import error_response, success_response



# ---------------------------------------------------------------------------
# Mẫu override từng func — mỗi func minh hoạ 1 pattern + TODO tiếng Việt.
# Header thật: copy func cần custom, xoá func không cần (dùng base mặc định).
# ---------------------------------------------------------------------------

def definition(request, header, params=None):
	# TODO: thêm/bớt viewSelector, search.options, details.columns, chart.charts
	# theo nghiệp vụ của header mới. Mẫu tối giản: gọi base.
	return base_system.definition(request, header, params)


def details(request, header, params=None):
	# Mẫu 0 viết TIẾNG VIỆT TRỰC TIẾP trong payload nên không cần dịch —
	# nhưng base tự bỏ qua khi TRANSLATIONS rỗng, cứ gọi như bình thường.
	# TODO: header thật có marker @ thì giữ nguyên dòng này (base tự dịch).
	return base_system.details(request, header, params)


def search(request, header, params=None):
	# TODO: nối ORM thật. Mẫu demo: lọc table_data theo query.details.
	query = params or {}
	wanted = (query.get('details') or {}).get('vendorCode')
	_payload = base_system._load_details_payload(header)
	_table = ((_payload or {}).get('data') or {}).get('table') or {}
	rows = list(_table.get('table_data') or [])
	if wanted:
		rows = [row for row in rows if wanted.lower() in str(row.get('vendorCode', '')).lower()]
	limit = int(query.get('limit') or 50)
	offset = int(query.get('offset') or 0)
	total = len(rows)
	return success_response(
		data={
			'table': {'table_data': rows[offset:offset + limit]},
			'total_rows': total,
			'query': query,
		},
		message=_('Search completed.'),
	)


def chart(request, header, params=None):
	# TODO: tính labels/values từ data thật. Mẫu demo: đếm Đạt/Không đạt.
	_payload = base_system._load_details_payload(header)
	_table = ((_payload or {}).get('data') or {}).get('table') or {}
	rows = list(_table.get('table_data') or [])
	pass_count = sum(1 for row in rows if row.get('pic') == 'SYSTEM')
	return success_response(
		data={'labels': ['Đạt', 'Không đạt'], 'values': [pass_count, len(rows) - pass_count]},
		message=_('Chart loaded.'),
	)


def action(request, header, params=None):
	# TODO: đăng ký verb mới theo mẫu if dưới đây.
	func = (params or {}).get('func')
	if func == 'view_detail':
		return success_response(
			data={'record_id': (params or {}).get('record_id')},
			message=_('Details loaded.'),
		)
	return error_response(
		message=_("Function '%(func)s' not found in system %(id)s.") % {'func': func, 'id': header.id},
		status=status.HTTP_404_NOT_FOUND,
	)


def download(request, header, params=None):
	# TODO: nối file thật (Excel/CSV). Mẫu demo: trả CSV 1 dòng.
	from django.http import HttpResponse

	content = 'no,vendorCode,vendorName\n1,DK01,CÔNG TY MẪU SỐ 1\n'
	response = HttpResponse(content, content_type='text/csv; charset=utf-8')
	response['Content-Disposition'] = 'attachment; filename="header-10000-demo.csv"'
	return response


def dashboard(request, header, params=None):
	# TODO: nối KPI thật. Mẫu demo: đếm từ data demo.
	_payload = base_system._load_details_payload(header)
	_table = ((_payload or {}).get('data') or {}).get('table') or {}
	rows = list(_table.get('table_data') or [])
	return success_response(
		data={
			'kpi_summary': [
				{'label': 'Tổng số', 'value': str(len(rows)), 'trend': 'up'},
				{'label': 'Đạt', 'value': str(sum(1 for row in rows if row.get('pic') == 'SYSTEM')), 'trend': 'up'},
			],
		},
		message=_('Dashboard loaded.'),
	)


class Header10000DetailsView(APIView):
	"""POST /api/v1/systems/details/10000 — endpoint TEST RIÊNG của header demo."""

	# Header mà endpoint này bảo vệ — HasHeaderPermission đọc attr này;
	# header demo 10000 được bypass (không tra DB).
	header_id = 10000
	permission_classes = [permissions.IsAuthenticated, HasHeaderPermission]
	throttle_classes = [ScopedRateThrottle]
	throttle_scope = 'systems'
	http_method_names = ['post', 'options']

	@extend_schema(
		tags=['Systems Details'],
		request=Header10000DetailsRequestSerializer,
		responses={200: dict},
	)
	def post(self, request):
		serializer = Header10000DetailsRequestSerializer(data=request.data or {})
		serializer.is_valid(raise_exception=True)
		body = serializer.validated_data

		# Header demo: dựng tại chỗ, KHÔNG get_object_or_404 DB.
		from types import SimpleNamespace

		header = SimpleNamespace(
			id=10000,
			header_vi='Header Demo 10000',
			header_en='Header Demo 10000',
			header_kr='데모 헤더 10000',
			view_vi='Demo',
			is_mobile=False,
		)
		try:
			params = {'scope': body['scope'], 'query': body['query']}
			return details(request, header=header, params=params)
		except Exception:
			return error_response(
				message=_('System function execution failed.'),
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)
