"""Test phân trang `details`/`search` — chống input rác gây 500 hoặc cắt list ngược.

Bug gốc: `limit`/`offset` đến từ query string (luôn là chuỗi) nhưng được `int()`
thẳng không bọc try ⇒ `"abc"` ném ValueError ⇒ HTTP 500; giá trị âm cắt list
NGƯỢC (`rows[-1:-1+limit]`) trả sai dữ liệu.
"""

import importlib
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.systems.systems_details import base_system

# Thư mục `10000` BẮT ĐẦU BẰNG CHỮ SỐ ⇒ không import được bằng dotted path
# (`apps.systems.systems_details.10000` là cú pháp sai), phải qua importlib.
v10000 = importlib.import_module("apps.systems.systems_details.10000.views")


def _payload(n_rows=10):
	return {
		"data": {
			"table": {"table_data": [{"vendorCode": f"V{i:03d}", "pic": "SYSTEM"} for i in range(n_rows)]},
		}
	}


HEADER = SimpleNamespace(id=10000)


def _rows(response):
	"""Rút danh sách dòng từ success_response (dùng chung details và search)."""
	return response.data["data"]["table"]["table_data"]


class DetailsPaginationTests(SimpleTestCase):
	def _details(self, query, n_rows=10):
		with patch.object(base_system, "_load_details_payload", return_value=_payload(n_rows)):
			return base_system.details(None, header=HEADER, params={"query": query})

	def test_garbage_limit_falls_back_instead_of_500(self):
		"""`limit="abc"` phải rơi về mặc định thay vì ném ValueError ⇒ 500."""
		self.assertEqual(len(_rows(self._details({"limit": "abc"}))), 10)

	def test_negative_limit_does_not_reverse_slice(self):
		"""`limit=-5` trước đây ⇒ `rows[-1:-1+50]` trả dữ liệu sai, nay về mặc định 50."""
		self.assertEqual(len(_rows(self._details({"limit": -5}))), 10)

	def test_negative_offset_treated_as_zero(self):
		"""`offset=-10` phải tương đương offset=0, không phải đếm từ cuối list."""
		out = self._details({"limit": 3, "offset": -10})
		self.assertEqual([r["vendorCode"] for r in _rows(out)], ["V000", "V001", "V002"])

	def test_limit_capped_at_max(self):
		out = self._details({"limit": 999999}, n_rows=1000)
		self.assertLessEqual(len(_rows(out)), base_system.MAX_PAGE_SIZE)

	def test_total_rows_reflects_full_dataset_not_page(self):
		"""total_rows phải là TỔNG số dòng, không phải số dòng của trang hiện tại."""
		out = self._details({"limit": 5}, n_rows=10)
		self.assertEqual(out.data["data"]["total_rows"], 10)

	def test_offset_beyond_end_returns_empty_not_error(self):
		out = self._details({"limit": 5, "offset": 999}, n_rows=10)
		self.assertEqual(_rows(out), [])


class SearchPaginationTests(SimpleTestCase):
	def _search(self, query, n_rows=10):
		with patch.object(base_system, "_load_details_payload", return_value=_payload(n_rows)):
			return v10000.search(None, header=HEADER, params=query)

	def test_garbage_limit_does_not_raise(self):
		self.assertEqual(_rows(self._search({"limit": "xyz"})), _rows(self._search({})))

	def test_negative_offset_does_not_reverse(self):
		"""offset âm phải bị chặn về 0 (lấy từ đầu), không lấy 5 dòng cuối."""
		out = _rows(self._search({"limit": 5, "offset": -1}))
		self.assertEqual([r["vendorCode"] for r in out], ["V000", "V001", "V002", "V003", "V004"])

	def test_limit_capped_at_max(self):
		self.assertLessEqual(len(_rows(self._search({"limit": 10**9}, n_rows=1000))), base_system.MAX_PAGE_SIZE)

	def test_filter_then_paginate_keeps_total_of_filtered_rows(self):
		"""total_rows phải đếm SAU khi lọc, khớp với số dòng client sẽ thấy."""
		# Lọc chính xác 2 dòng (V001, V007) — "V00" sẽ khớp cả V009 nên
		# không dùng làm mẫu vì đó là substring, không phải bug.
		out = self._search({"details": {"vendorCode": "V001"}})
		self.assertEqual(out.data["data"]["total_rows"], 1)

	def test_filter_is_case_insensitive_substring(self):
		"""Lọc là substring không phân biệt hoa thường — hành vi có chủ đích."""
		out = self._search({"details": {"vendorCode": "v001"}})
		self.assertEqual(out.data["data"]["total_rows"], 1)