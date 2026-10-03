"""
Unit tests cho `submit_form` (dialog SUBMIT_FORM) + chuẩn hoá input của dispatcher.

Không cần DB: `submit_form` chỉ đọc payload tĩnh (module payload.py) + request/header
được stub bằng SimpleNamespace; dispatcher gọi trực tiếp với `get_object_or_404` đã patch.

Chạy:  python -m pytest tests/test_systems_submit.py -q
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from apps.systems.systems_details.base_system import _collect_files, submit_form
from apps.systems.views import SystemDispatchView

HEADER = SimpleNamespace(id=1, header_vi="IQC", header_en="IQC", header_kr="IQC", view_vi="v", is_mobile=False)
USER = SimpleNamespace(id=1)


def make_request(data=None, files=None):
    """Request giả đủ dùng cho submit_form (không cần DRF/DB)."""
    request = SimpleNamespace(user=USER, LANGUAGE_CODE="vi")
    request.data = data or {}
    request.FILES = files or {}
    return request


def valid_params(**overrides):
    params = {
        "header_id": 1,
        "dialog_id": "dlg_input_system",
        "action_id": "dlg_input_system.save",
        "values": {"Vendor Sorting": "ABC"},
        "files": [],
        "query": {"limit": 5, "offset": 0},
    }
    params.update(overrides)
    return params


class SubmitFormTests(SimpleTestCase):
    """Validate + echo của submit_form (mặc định SYSTEMS_SUBMIT_DEFAULT=echo)."""

    def test_valid_submit_echoes_values(self):
        response = submit_form(make_request(), HEADER, valid_params())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertFalse(response.data["data"]["persisted"])
        self.assertEqual(response.data["data"]["echo"]["values"], {"Vendor Sorting": "ABC"})
        self.assertEqual(response.data["meta"]["dev_echo"], True)

    def test_header_mismatch_rejected(self):
        response = submit_form(make_request(), HEADER, valid_params(header_id=2))
        self.assertEqual(response.status_code, 400)
        self.assertIn("header_id", response.data["errors"])

    def test_unknown_dialog_rejected(self):
        response = submit_form(make_request(), HEADER, valid_params(dialog_id="khong_co"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("dialog_id", response.data["errors"])

    def test_unknown_action_rejected(self):
        response = submit_form(make_request(), HEADER, valid_params(action_id="khong_co"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("action_id", response.data["errors"])

    def test_header_without_payload_returns_404(self):
        header = SimpleNamespace(id=99)
        response = submit_form(make_request(), header, valid_params(header_id=99))
        self.assertEqual(response.status_code, 404)

    @override_settings(SYSTEMS_SUBMIT_DEFAULT="reject")
    def test_reject_mode_returns_501(self):
        response = submit_form(make_request(), HEADER, valid_params())
        self.assertEqual(response.status_code, 501)

    @override_settings(SYSTEMS_UPLOAD_MAX_MB=0)
    def test_over_upload_limit_rejected(self):
        files = {"0": SimpleUploadedFile("a.pdf", b"abc", content_type="application/pdf")}
        params = valid_params(files=[{"__file_index": 0, "name": "a.pdf", "size": 3, "mime": "application/pdf"}])
        response = submit_form(make_request(files=files), HEADER, params)
        self.assertEqual(response.status_code, 400)
        self.assertIn("files", response.data["errors"])

    def test_multipart_files_are_mapped_and_echoed(self):
        files = {
            "0": SimpleUploadedFile("a.pdf", b"abc", content_type="application/pdf"),
            "1": SimpleUploadedFile("b.png", b"de", content_type="image/png"),
        }
        params = valid_params(
            files=[
                {"__file_index": 0, "name": "a.pdf", "size": 3, "mime": "application/pdf"},
                {"__file_index": 1, "name": "b.png", "size": 2, "mime": "image/png"},
            ]
        )
        response = submit_form(make_request(files=files), HEADER, params)
        self.assertEqual(response.status_code, 200)
        echoed = response.data["data"]["echo"]["files"]
        self.assertEqual([item["name"] for item in echoed], ["a.pdf", "b.png"])

    @override_settings(SYSTEMS_UPLOAD_MAX_MB=0)
    def test_client_metadata_cannot_bypass_size_limit(self):
        """Metadata khai size 0 nhưng file thật có dữ liệu → vẫn bị chặn (size lấy từ server)."""
        files = {"0": SimpleUploadedFile("a.pdf", b"abc")}
        params = valid_params(files=[{"__file_index": 0, "name": "a.pdf", "size": 0}])
        response = submit_form(make_request(files=files), HEADER, params)
        self.assertEqual(response.status_code, 400)
        self.assertIn("files", response.data["errors"])

    def test_metadata_without_actual_file_is_ignored(self):
        """Client khai có file nhưng không gửi file → không echo file 'ma'."""
        params = valid_params(files=[{"__file_index": 5, "name": "ghost.pdf", "size": 10}])
        response = submit_form(make_request(files={}), HEADER, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["echo"]["files"], [])

    def test_wrong_power_key_rejected(self):
        """power_key không thuộc dialog → 400 errors.power_key."""
        response = submit_form(make_request(), HEADER, valid_params(power_key=999))
        self.assertEqual(response.status_code, 400)
        self.assertIn("power_key", response.data["errors"])

    def test_correct_power_key_accepted(self):
        """power_key khớp table.power_actions[].key=1 → 200."""
        response = submit_form(make_request(), HEADER, valid_params(power_key=1))
        self.assertEqual(response.status_code, 200)

    def test_missing_power_key_still_accepted_demo(self):
        """Demo: thiếu power_key vẫn cho qua (P1.6 thật mới enforce)."""
        response = submit_form(make_request(), HEADER, valid_params())
        self.assertEqual(response.status_code, 200)

    def test_request_id_is_echoed(self):
        """request_id FE gửi (idempotency) được echo lại."""
        response = submit_form(make_request(), HEADER, valid_params(request_id="req-123"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["echo"]["request_id"], "req-123")


class DemoHeaderBypassTests(SimpleTestCase):
    """Header demo 10000 — bypass DB/quyền, chỉ validate theo payload."""

    DEMO_HEADER = SimpleNamespace(
        id=10000, header_vi="Header Demo 10000", header_en="Header Demo 10000",
        header_kr="demo", view_vi="Demo", is_mobile=False,
    )

    # `values` phải THỎA MÃN validate của payload 10000:
    #   - `action.validate.required` (base_system.py) liệt kê 7 field bắt buộc
    #   - section `table` có `validate.min_selected = 1` ⇒ phải có
    #     `selected_item_ids` (khoá trong `section.config.selected_key`)
    # Thiếu bất kỳ cái nào ⇒ BE trả 400 và test này fail vì lý do không liên
    # quan (trước đây chỉ gửi `vendor_code` nên luôn 400).
    VALID_VALUES = {
        "team": "22",
        "vendor_code": "DK01",
        "vendor_name": "DAE RIM",
        "inspection_date": "2026-01-15",
        "lot_no": "LOT001",
        "defect_qty": 0,
        "result_status": "pass",
        "selected_item_ids": ["1"],
    }

    def _demo_params(self, **overrides):
        params = valid_params(header_id=10000, values=dict(self.VALID_VALUES))
        params.update(overrides)
        return params

    def test_demo_submit_without_header_id_in_params(self):
        """Demo: FE không gửi params.header_id vẫn echo 200 (tự lấy header.id)."""
        params = self._demo_params()
        del params["header_id"]
        response = submit_form(make_request(), self.DEMO_HEADER, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["echo"]["header_id"], 10000)

    def test_demo_submit_wrong_header_rejected(self):
        """Demo gửi lệch sang header thật → 400 (chống submit lệch)."""
        response = submit_form(make_request(), self.DEMO_HEADER, self._demo_params(header_id=1))
        self.assertEqual(response.status_code, 400)
        self.assertIn("header_id", response.data["errors"])

    def test_demo_wrong_power_key_rejected(self):
        """Demo không tra PowerPermission DB nhưng sai key payload vẫn 400."""
        response = submit_form(make_request(), self.DEMO_HEADER, self._demo_params(power_key=999))
        self.assertEqual(response.status_code, 400)
        self.assertIn("power_key", response.data["errors"])

    def test_demo_dispatcher_without_db(self):
        """Dispatcher header 10000 không cần SystemHeader trong DB."""
        request = make_request(data={"header_id": 10000, "func": "details", "params": {"scope": "data"}})
        with patch("apps.systems.views.get_object_or_404") as get_mock:
            response = SystemDispatchView().post(request)
        get_mock.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])


class CollectFilesTests(SimpleTestCase):
    """Ghép metadata FE gửi ↔ request.FILES (kể cả khi client không gửi metadata)."""

    def test_metadata_order_is_respected(self):
        files = {"0": SimpleUploadedFile("a.pdf", b"abc"), "1": SimpleUploadedFile("b.png", b"de")}
        collected = _collect_files(make_request(files=files), {"files": [{"__file_index": 1}, {"__file_index": 0}]})
        self.assertEqual([item["name"] for item in collected], ["b.png", "a.pdf"])

    def test_files_without_metadata_are_included(self):
        files = {"0": SimpleUploadedFile("a.pdf", b"abc")}
        collected = _collect_files(make_request(files=files), {})
        self.assertEqual(len(collected), 1)
        self.assertEqual(collected[0]["name"], "a.pdf")


class DispatchInputNormalizationTests(SimpleTestCase):
    """Dispatcher: multipart gửi header_id dạng chuỗi + params dạng JSON string."""

    def _post(self, data):
        request = make_request(data=data)
        with patch("apps.systems.views.get_object_or_404", return_value=HEADER):
            return SystemDispatchView().post(request)

    def test_multipart_string_header_id_and_json_params(self):
        response = self._post(
            {
                "header_id": "1",
                "func": "details",
                "params": json.dumps({"scope": "data", "query": {"limit": 5, "offset": 0}}),
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])

    def test_invalid_params_json_returns_400(self):
        response = self._post({"header_id": "1", "func": "details", "params": "{khong-phai-json}"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("params", response.data["message"])

    def test_non_numeric_header_id_returns_400(self):
        response = self._post({"header_id": "abc", "func": "details"})
        self.assertEqual(response.status_code, 400)

    def test_missing_func_returns_400(self):
        response = self._post({"header_id": "1"})
        self.assertEqual(response.status_code, 400)