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
    """Schema cấu hình UI: search fields, columns, actions, charts."""
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
                "fields": [
                    {"field": "code", "label": _("Code"), "field_type": "text"},
                    {"field": "date", "label": _("Date"), "field_type": "date"},
                ],
            },
            "details": {
                "columns": [
                    {"field": "code", "label": _("Code"), "renderer": "text"},
                    {"field": "name", "label": _("Name"), "renderer": "text"},
                    {"field": "status", "label": _("Status"), "renderer": "status"},
                    {"field": "date", "label": _("Date"), "renderer": "date"},
                    {"field": "value", "label": _("Value"), "renderer": "number"},
                ],
                "actions": [
                    {"action_id": "view_detail", "label": _("Detail")},
                    {"action_id": "edit_record", "label": _("Edit")},
                ],
            },
            "charts": {
                "charts": [
                    {"chart_id": "pass_fail_ratio", "title": _("Pass/Fail Ratio"), "chart_type": "pie"},
                    {"chart_id": "daily_trend", "title": _("Daily Trend"), "chart_type": "line"},
                ],
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