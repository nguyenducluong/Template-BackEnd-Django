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

from django.utils.translation import gettext as _

from libs.responses import error_response, success_response
from apps.systems.systems_details.translations import translate_payload


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
    rows, total, page, page_size = _mock_rows(header, params or {})
    return success_response(
        data={
            "rows": rows,
            "pagination": {"page": page, "page_size": page_size, "total": total},
        },
        message=_("Search completed"),
    )


def chart(request, header, params=None):
    """Dữ liệu biểu đồ theo chart_id trong params."""
    chart_cfg = (params or {}).get("chart") or {}
    chart_id = chart_cfg.get("id", "pass_fail_ratio")
    if chart_id == "pass_fail_ratio":
        data = {"labels": ["PASS", "FAIL"], "values": [72, 28]}
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
    # TODO: triển khai nghiệp vụ thật tại đây theo từng hệ thống.
    return success_response(
        data={"action_id": action_id, "record_id": record_id, "applied": True},
        message=_("Action executed"),
    )


def download(request, header, params=None):
    """Xuất file (CSV/Excel) — trả URL hoặc file response."""
    fmt = (params or {}).get("format", "csv")
    # TODO: sinh file thật bằng openpyxl/csv rồi trả FileResponse.
    return success_response(
        data={"format": fmt, "file_url": f"/media/exports/{header.id}/export.{fmt}"},
        message=_("Export queued"),
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

    # ---- Chuẩn bị data phẳng dùng chung cho cả 2 scope (deepcopy — không bẩn module dict) ----
    import copy

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

    # Multilanguage riêng của systems_details — dịch marker "@key" theo lang
    data = translate_payload(data, lang, header.id)
    return success_response(data=data, message=message)
