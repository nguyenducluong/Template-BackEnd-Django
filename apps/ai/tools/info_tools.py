"""
Tools đọc dữ liệu Info: header menu, tổ chức.
Dùng apps.info.models — theo read (authenticated).
"""
from __future__ import annotations

from .base import ToolSpec


def _header_structure_handler(user, args: dict) -> dict:
    from apps.info.models import GroupHeader, PagesHeader, SystemHeader

    groups = []
    for g in GroupHeader.objects.filter(is_use=True).order_by("sort", "id"):
        pages = []
        for p in g.pages.filter(is_use=True).order_by("sort", "id"):
            pages.append({
                "id": p.id,
                "page_vi": p.page_vi,
                "page_en": p.page_en,
                "page_kr": p.page_kr,
                "headers": list(p.system_headers.filter(is_use=True)
                                .order_by("sort", "id")
                                .values("id", "view_vi", "view_en", "view_kr",
                                        "header_vi", "header_en", "header_kr", "sort")),
            })
        groups.append({
            "id": g.id,
            "group_vi": g.group_vi,
            "group_en": g.group_en,
            "group_kr": g.group_kr,
            "pages": pages,
        })
    return {"groups": groups}


def _orgs_handler(user, args: dict) -> dict:
    from apps.info.models import Organization

    level = args.get("level")
    qs = Organization.objects.all()
    if level is not None:
        qs = qs.filter(level=level)
    qs = qs.order_by("sort", "id")
    return {
        "orgs": [{
            "id": o.id, "name": o.name, "level": o.level,
            "parent_id": o.parent_id, "full_path": o.full_path,
            "is_use": o.is_use,
        } for o in qs[:200]],
    }


def _org_tree_handler(user, args: dict) -> dict:
    from apps.info.models import Organization

    def build(node):
        return {
            "id": node.id,
            "name": node.name,
            "children": [build(c) for c in node.children.order_by("sort", "id")],
        }

    roots = Organization.objects.filter(parent__isnull=True).order_by("sort", "id")
    return {"tree": [build(r) for r in roots[:100]]}


header_structure_tool = ToolSpec(
    name="info.header_structure",
    description="Lấy cây menu header hệ thống (Group -> Pages -> SystemHeader) đang bật.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_header_structure_handler,
)

orgs_tool = ToolSpec(
    name="info.orgs",
    description="Danh sách tổ chức (bộ phận), lọc theo level (0=Team,1=Group,2=Part,3=Location).",
    input_schema={
        "type": "object",
        "properties": {"level": {"type": "integer", "minimum": 0, "maximum": 3}},
        "additionalProperties": False,
    },
    handler=_orgs_handler,
)

org_tree_tool = ToolSpec(
    name="info.org_tree",
    description="Cây tổ chức phân cấp (root -> children), dùng cached_full_path.",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    handler=_org_tree_handler,
)