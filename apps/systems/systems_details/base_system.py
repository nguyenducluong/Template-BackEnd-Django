"""
Base system helpers — dùng chung cho mọi folder ``systems_details/{header_id}/``.

Mỗi hệ thống override các hàm này trong ``views.py`` của mình khi cần logic
nghiệp vụ riêng; hàm không override sẽ trả mock data an toàn.

Chữ ký chuẩn của mọi func trong views.py:

    def func(request, header, params=None): ...

- ``request``  : DRF request (đã auth).
- ``header``   : instance ``apps.info.models.SystemHeader``.
- ``params``   : dict từ POST body (tùy chọn).
- return       : DRF Response — thường qua ``success_response``.
"""

import copy
import importlib
import logging

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework import status

from libs.responses import error_response, success_response
from apps.systems.systems_details.translations import translate_payload

logger = logging.getLogger("apps")


# ---------------------------------------------------------------------------
# Mock generators (thay bằng query thật khi triển khai nghiệp vụ)
# ---------------------------------------------------------------------------
def _mock_rows(header, params, total=120):
    """Sinh mock rows cho search — demo thôi, thay bằng ORM query thật."""
    page = (params.get("pagination") or {}).get("page", 1)
    page_size = (params.get("pagination") or {}).get("page_size", 20)
    start = (page - 1) * page_size
    rows = [
        {
            "id": start + i + 1,
            "code": f"{header.id}-{start + i + 1:05d}",
            "name": f"{header.header_vi} - Item {start + i + 1}",
            "status": "PASS" if (start + i) % 3 else "FAIL",
            "date": "2026-09-17",
            "value": (start + i + 1) * 100,
        }
        for i in range(min(page_size, max(total - start, 0)))
    ]
    return rows, total, page, page_size


# ---------------------------------------------------------------------------
# Các func mặc định — mỗi hệ thống override trong views.py khi cần
# ---------------------------------------------------------------------------
def definition(request, header, params=None):
    """Schema cấu hình UI của UI Engine — đúng contract Schema/Runtime.

    schema.search.viewSelector : { enabled, default, options } — cấu hình nút
        chuyển Details/Chart trên toolbar; runtime.viewMode khởi tạo từ `default`.
    schema.search.org          : { label, type, options } — bộ lọc đơn vị;
        giá trị lưu runtime.search.org.selected (array khi type='multi').
    schema.search.date         : { label, type: 'range'|'single' } — bộ lọc ngày;
        giá trị lưu runtime.search.date { type, from, to }.
    schema.search.options      : { fields: [...] } — các trường tìm kiếm động,
        render qua fieldRegistry; giá trị lưu runtime.search.options[field].
    schema.details             : columns / actions / pageSizeOptions.
    schema.chart.charts        : danh sách biểu đồ { chart_id, title, chart_type, span? }.
    schema.history.enabled     : ẩn/hiện cột WindowManager bên phải.
    """
    return success_response(
        data={
            "system": {
                "id": header.id,
                "code": f"SYS-{header.id}",
                "name": header.header_vi,
                "name_en": header.header_en,
                "name_kr": header.header_kr,
                "view": header.view_vi,
                "is_mobile": header.is_mobile,
            },
            "search": {
                "viewSelector": {
                    "enabled": True,
                    "default": "details",
                    "options": [
                        {"value": "details", "label": _("Details")},
                        {"value": "chart", "label": _("Chart")},
                    ],
                },
                "org": {
                    "label": _("Org"),
                    "type": "multi",
                    "options": [
                        {"value": "ORG-01", "label": "ORG-01"},
                        {"value": "ORG-02", "label": "ORG-02"},
                    ],
                },
                "date": {
                    "label": _("Date"),
                    "type": "range",
                },
                "options": {
                    "fields": [
                        {"field": "code", "label": _("Code"), "field_type": "text"},
                        {
                            "field": "status",
                            "label": _("Status"),
                            "field_type": "select",
                            "options": [
                                {"value": "PASS", "label": "PASS"},
                                {"value": "FAIL", "label": "FAIL"},
                            ],
                        },
                    ],
                },
            },
            "details": {
                "columns": [
                    {"field": "code", "label": _("Code"), "renderer": "text", "sortable": True},
                    {"field": "name", "label": _("Name"), "renderer": "text"},
                    {"field": "status", "label": _("Status"), "renderer": "status"},
                    {"field": "date", "label": _("Date"), "renderer": "date"},
                    {"field": "value", "label": _("Value"), "renderer": "number"},
                ],
                "actions": [
                    {"action_id": "view_detail", "label": _("Detail")},
                    {"action_id": "edit_record", "label": _("Edit")},
                ],
                "pageSizeOptions": [20, 50, 100],
            },
            "chart": {
                "charts": [
                    {"chart_id": "pass_fail_ratio", "title": _("Pass/Fail Ratio"), "chart_type": "pie"},
                    {"chart_id": "daily_trend", "title": _("Daily Trend"), "chart_type": "line"},
                ],
            },
            "history": {
                "enabled": True,
            },
        },
        message=_("System definition loaded"),
    )

def search(request, header, params=None):
    """Tìm kiếm dữ liệu — trả rows + pagination theo chuẩn UI Engine."""
    # TODO(header 1): noi ORM that khi co model. Mau demo: phan trang tren
    # data demo rut tu payload (table_data) + loc theo query.details.vendorCode.
    _payload = _load_details_payload(header)
    _table = ((_payload or {}).get("data") or {}).get("table") or {}
    _rows = list(_table.get("table_data") or [])
    _query = params.get("query") if isinstance(params, dict) else {}
    _query = _query if isinstance(_query, dict) else {}
    _wanted = (_query.get("details") or {}).get("vendorCode")
    if _wanted:
        _rows = [r for r in _rows if _wanted.lower() in str(r.get("vendorCode", "")).lower()]
    try:
        _limit = int(_query.get("limit") or 50)
    except (TypeError, ValueError):
        _limit = 50
    try:
        _offset = int(_query.get("offset") or 0)
    except (TypeError, ValueError):
        _offset = 0
    _limit = max(1, min(_limit, 200))
    _offset = max(0, _offset)
    rows, total = _rows[_offset:_offset + _limit], len(_rows)
    return success_response(
        data={
            "table": {"table_data": rows},
            "total_rows": total,
            "query": _query,
        },
        message=_("Search completed"),
    )


def chart(request, header, params=None):
    """Dữ liệu biểu đồ theo chart_id trong params."""
    chart_cfg = (params or {}).get("chart") or {}
    chart_id = chart_cfg.get("id", "pass_fail_ratio")
    if chart_id == "pass_fail_ratio":
        _payload = _load_details_payload(header)
        _table = ((_payload or {}).get("data") or {}).get("table") or {}
        _rows = _table.get("table_data") or []
        _pass = sum(1 for r in _rows if r.get("pic") == "SYSTEM")
        data = {"labels": ["PASS", "FAIL"], "values": [_pass, len(_rows) - _pass]}
    else:
        data = {"labels": ["Mon", "Tue", "Wed", "Thu", "Fri"], "values": [12, 19, 8, 25, 22]}
    return success_response(
        data={"chart_id": chart_id, **data},
        message=_("Chart data loaded"),
    )


def action(request, header, params=None):
    """Thực hiện action trên 1 row (edit / delete / approve...)."""
    action_cfg = (params or {}).get("action") or {}
    action_id = action_cfg.get("action_id")
    record_id = action_cfg.get("record_id")
    if not action_id or not record_id:
        return error_response(
            message=_("Fields 'action_id' and 'record_id' are required."),
            status=400,
        )
    # CHƯA triển khai nghiệp vụ thật → trả 501 rõ ràng.
    # Trước đây trả success với applied=True (giả) khiến client tưởng action
    # đã được áp dụng thành công. Mỗi hệ thống override hàm này khi làm thật.
    return error_response(
        message=_("This action is not implemented for this system yet."),
        status=status.HTTP_501_NOT_IMPLEMENTED,
    )


def download(request, header, params=None):
    """Xuất file (CSV/Excel) — trả URL hoặc file response."""
    fmt = (params or {}).get("format", "csv")
    # CHƯA sinh file thật (openpyxl/csv + FileResponse) → trả 501 thay vì
    # success kèm file_url giả (/media/exports/... không tồn tại).
    return error_response(
        message=_("Export is not implemented for this system yet (format: %(format)s).")
        % {"format": fmt},
        status=status.HTTP_501_NOT_IMPLEMENTED,
    )


def dashboard(request, header, params=None):
    """Số liệu tổng quan cho dashboard của hệ thống."""
    return success_response(
        data={
            "system": {"id": header.id, "name": header.header_vi},
            "cards": [
                {"key": "total", "label": _("Total"), "value": 120},
                {"key": "pass", "label": _("Passed"), "value": 86},
                {"key": "fail", "label": _("Failed"), "value": 34},
            ],
            "trend": {"labels": ["Mon", "Tue", "Wed", "Thu", "Fri"], "values": [10, 14, 9, 22, 18]},
        },
        message=_("Dashboard loaded"),
    )


# ---------------------------------------------------------------------------
# Details view — dữ liệu blueprint {config, data, initial_state} theo header
# ---------------------------------------------------------------------------
def _load_details_payload(header):
    """Import ``payload.DETAILS`` của systems_details/{header_id}/. Trả None nếu chưa có."""
    import importlib

    try:
        module = importlib.import_module(f"apps.systems.systems_details.{header.id}.payload")
    except ModuleNotFoundError:
        return None
    return module.DETAILS


def _build_history(payload):
    """Sinh history entry mặc định đúng shape frontend (HistoryApp/ModalDragable)."""
    dialogs = ((payload or {}).get("config") or {}).get("dialogs") or {}
    active_id = (((payload or {}).get("initial_state") or {}).get("current") or {}).get("active_dialog_id")
    label = (dialogs.get(active_id) or {}).get("header", {}).get("label") or active_id
    return [{"label": label, "color": "success", "is_active": True, "dialog_id": active_id, "row": [], "data": {}}]


def details(request, header, params=None):
    """Dữ liệu view chi tiết theo header — đọc từ payload.py riêng của từng hệ thống.

    params.scope:
        - 'full' : trả phẳng { config, initial_state, search, table, total_rows, history }
                   — dùng khi mới mở header (hydrates config + defaults + data).
        - 'data' (mặc định): { search, table, total_rows, history } — dùng cho search.

    params.query: {org, period, limit, offset, details} — áp phân trang cho bảng
    ``table_data`` và tính total_rows; các bảng KPI/grouped trả full (mock-safe).

    Cả 2 scope đều trả CÁC KEY PHẲNG như nhau (table/search/total_rows/history nằm
    trực tiếp trong data) để contract đồng nhất với detailsSlice.fulfilled.

    Multilanguage: payload được deepcopy + dịch theo request.LANGUAGE_CODE
    (Accept-Language từ frontend) bằng translations riêng của systems_details
    (KHÔNG dùng gettext locale) — trả client đã dịch, không bẩn module dict.
    """
    payload = _load_details_payload(header)
    if payload is None:
        return error_response(
            message=_("Details payload not implemented for this header."),
            status=404,
        )

    scope = (params or {}).get("scope") or "data"
    query = (params or {}).get("query") or {}
    lang = getattr(request, "LANGUAGE_CODE", None) or "vi"

    # ---- Chuẩn bị data phẳng dùng chung cho cả 2 scope ----
    # deepcopy: payload["data"] là dict TĨNH của module payload.py — phải copy trước
    # khi sửa (phân trang) để không làm bẩn payload của các request sau.
    data = copy.deepcopy(payload["data"])
    table = data.setdefault("table", {})
    rows = table.get("table_data") or []
    limit = int(query.get("limit") or 50)
    offset = int(query.get("offset") or 0)
    table["table_data"] = rows[offset : offset + limit]
    data["total_rows"] = len(rows)
    data["history"] = _build_history(payload)

    if scope == "full":
        # Thêm config blueprint + initial_state (defaults/current) cho lần đầu mở header
        data["config"] = copy.deepcopy(payload["config"])
        data["initial_state"] = copy.deepcopy(payload["initial_state"])
        message = _("Details loaded")
    else:
        message = _("Details data loaded")

    # Multilanguage riêng của systems_details — dịch marker "@key" theo lang.
    # copy_payload=False: `data` đã là bản deepcopy ở trên nên KHÔNG copy lần 2
    # (translate_details tự dựng dict/list mới ⇒ vẫn an toàn, không bẩn module dict).
    data = translate_payload(data, lang, header.id, copy_payload=False)
    return success_response(data=data, message=message)


# ---------------------------------------------------------------------------
# Dialog actions — SUBMIT_FORM
# ---------------------------------------------------------------------------
def _collect_files(request, params):
    """Ghép file upload (multipart) ↔ metadata FE gửi trong ``params.files``.

    FE (`STD/src/axios/axios.jsx::build_form_data`) gửi file ở FormData key "0","1",…
    và để lại metadata ``{__file_index, name, size, mime}`` trong ``params.files``.
    Client không gửi metadata → suy ra từ chính ``request.FILES``.

    Returns:
        list[dict]: [{file, name, size, mime}]
    """
    uploads = getattr(request, "FILES", None) or {}
    metadata = [item for item in ((params or {}).get("files") or []) if isinstance(item, dict)]

    collected = []
    used_keys = set()
    for item in metadata:
        index = item.get("__file_index")
        upload = uploads.get(str(index)) if index is not None else None
        used_keys.add(str(index))
        # Client khai metadata nhưng KHÔNG gửi file tương ứng → bỏ (không echo file ma)
        if upload is None:
            continue
        collected.append(
            {
                "file": upload,
                "name": getattr(upload, "name", None) or item.get("name"),
                # Size lấy từ file SERVER nhận được — metadata của client có thể sai/giả
                # (dùng để chặn vượt hạn mức upload, không thể tin dữ liệu client).
                "size": getattr(upload, "size", None) or item.get("size") or 0,
                "mime": getattr(upload, "content_type", None) or item.get("mime"),
            }
        )
    for key, upload in uploads.items():
        if key in used_keys:
            continue
        collected.append(
            {
                "file": upload,
                "name": upload.name,
                "size": upload.size,
                "mime": getattr(upload, "content_type", None),
            }
        )
    return collected


def submit_form(request, header, params=None):
    """Nhận dữ liệu submit của dialog — mặc định ECHO (hệ thống chưa có nơi lưu).

    Contract (FE gửi trong ``params``)::

        {header_id, dialog_id, action_id, record_id?, values{}, files[], query{}}

    Validate L1 (không tin client): header_id trùng header đang xử lý · dialog_id tồn
    tại trong ``config.dialogs`` · action_id nằm trong ``actions`` của dialog · field
    trong ``action.validate.required`` phải có giá trị · tổng file ≤
    ``settings.SYSTEMS_UPLOAD_MAX_MB``.

    Lưu trữ: ``settings.SYSTEMS_SUBMIT_DEFAULT`` = "echo" (mặc định, dev) | "reject"
    (501 — khuyến nghị production khi chưa cấu hình). Hệ thống có nơi lưu thật thì
    override hàm này trong ``systems_details/{id}/views.py``.

    NOTE: kiểm tra quyền theo nút (``power_key``) bổ sung ở P1.6 cùng
    ``apps/info/permissions.py``.
    """
    params = params or {}
    # 0. Validate hinh thuc qua SubmitFormSerializer cua header (neu co).
    try:
        _smod = importlib.import_module("apps.systems.systems_details.%s.serializers" % header.id)
        _scls = getattr(_smod, "SubmitFormSerializer", None)
    except ModuleNotFoundError:
        _scls = None
    if _scls is not None:
        _ser = _scls(data=params)
        if not _ser.is_valid():
            return error_response(
                message=_("Invalid submit data."),
                errors=_ser.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        params = _ser.validated_data
    payload = _load_details_payload(header)
    if payload is None:
        return error_response(
            message=_("Details payload not implemented for this header."),
            status=status.HTTP_404_NOT_FOUND,
        )

    config = payload.get("config") or {}
    dialogs = config.get("dialogs") or {}
    current = ((payload.get("initial_state") or {}).get("current")) or {}
    # Header demo (DEMO_HEADER_IDS) khong co row SystemHeader trong DB nen
    # bo qua check trung DB o buoc 1 — chi yeu cau params.header_id khop
    # demo id neu FE gui kem (chong submit lech sang header that).
    from apps.info.permissions import DEMO_HEADER_IDS as _DEMO_IDS

    _is_demo = header.id in _DEMO_IDS
    errors = {}

    # 1. header_id phải trùng header đang xử lý (chống submit lệch hệ thống)
    submitted_header_id = params.get("header_id")
    if _is_demo and submitted_header_id is None:
        submitted_header_id = header.id
    if submitted_header_id is not None and str(submitted_header_id) != str(header.id):
        errors["header_id"] = [_("Submitted header does not match the current system.")]

    # 2. dialog_id phải có trong config của header
    dialog_id = params.get("dialog_id") or current.get("active_dialog_id")
    dialog_cfg = dialogs.get(dialog_id)
    if not dialog_cfg:
        errors["dialog_id"] = [
            _("Dialog '%(id)s' is not configured for this system.") % {"id": dialog_id}
        ]

    # 3a. power_key (demo): neu FE gui thi phai khop key trong
    # dialog.power_actions hoac config.table.power_actions; thieu thi bo qua.
    power_key = params.get("power_key")
    if power_key is not None and dialog_cfg:
        valid_keys = [it.get("key") for it in (dialog_cfg.get("power_actions") or [])]
        table_keys = [it.get("key") for it in (config.get("table") or {}).get("power_actions") or []]
        if power_key not in (valid_keys + table_keys):
            errors["power_key"] = [
                _("Power key %(key)s is not allowed for this dialog.") % {"key": power_key}
            ]

    # 3. action_id phải nằm trong actions của dialog
    action_id = params.get("action_id")
    action_cfg = None
    if dialog_cfg and action_id:
        action_cfg = next(
            (item for item in (dialog_cfg.get("actions") or []) if item.get("action_id") == action_id),
            None,
        )
        if action_cfg is None:
            errors["action_id"] = [
                _("Action '%(id)s' is not configured for this dialog.") % {"id": action_id}
            ]

    # 4. Field bắt buộc theo config của action
    values = params.get("values") or {}
    required_keys = ((action_cfg or {}).get("validate") or {}).get("required") or []
    missing = [key for key in required_keys if values.get(key) in (None, "", [], {})]
    if missing:
        errors["values"] = [
            _("Missing required field(s): %(fields)s.") % {"fields": ", ".join(missing)}
        ]

    # 5. Giới hạn dung lượng file — tổng size lấy từ FILE SERVER NHẬN ĐƯỢC
    # (xem _collect_files), không dùng số client khai trong params.files.
    files = _collect_files(request, params)
    max_mb = getattr(settings, "SYSTEMS_UPLOAD_MAX_MB", 15)
    total_size = sum(int(item.get("size") or 0) for item in files)
    if total_size > max_mb * 1024 * 1024:
        errors["files"] = [_("Attachments exceed the limit of %(mb)s MB.") % {"mb": max_mb}]

    if errors:
        return error_response(
            message=_("Invalid submit data."),
            errors=errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---- Mặc định: hệ thống chưa cấu hình nơi lưu ----
    mode = str(getattr(settings, "SYSTEMS_SUBMIT_DEFAULT", "echo")).lower()
    if mode == "reject":
        return error_response(
            message=_("This system has no submit handler configured yet."),
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    logger.info(
        "submit_form (echo — chưa lưu): user=%s header=%s dialog=%s action=%s files=%s",
        getattr(getattr(request, "user", None), "id", None),
        header.id,
        dialog_id,
        action_id,
        len(files),
    )
    return success_response(
        data={
            "persisted": False,
            "record_id": None,
            "affected_rows": 0,
            "echo": {
                "header_id": header.id,
                "dialog_id": dialog_id,
                "action_id": action_id,
                "record_id": params.get("record_id"),
                "values": values,
                "files": [
                    {"name": item.get("name"), "size": item.get("size"), "mime": item.get("mime")}
                    for item in files
                ],
                "query": params.get("query") or {},
                "submitted_at": timezone.now().isoformat(),
                "request_id": params.get("request_id") or None,
            },
        },
        message=_("Submit received but NOT stored (this system has no storage configured)."),
        meta={"status_code": 200, "dev_echo": True, "persisted": False},
    )
