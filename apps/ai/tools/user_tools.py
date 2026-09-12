"""
Tools đọc dữ liệu User (accounts.User, bảng _0010_user).

BẢO MẬT (S1): không expose PII xuyên user. Người dùng chỉ xem được:
  - chính bản thân, hoặc
  - user cùng org (khi có quyền), hoặc
  - bất kỳ user nào nếu có power `view_profile`.
knox_id (định danh dùng cho flow quên mật khẩu) CHỈ trả khi chính user
hoặc có power `view_profile`.
"""
from __future__ import annotations

from .base import ToolSpec, has_power

VIEW_PROFILE_POWER = "view_profile"


def _can_view(user, target) -> bool:
    """Kiểm tra quyền xem target user (càng ít query càng tốt)."""
    if target.id == user.id:
        return True
    if getattr(user, "org_id", None) and target.org_id == user.org_id:
        return True
    return has_power(user, [VIEW_PROFILE_POWER])


def _user_serialize(user, include_knox=False) -> dict:
    data = {
        "id": user.id,
        "gen_id": user.gen_id,
        "full_name": user.full_name,
        "status": user.status,
        "org": {"id": user.org_id, "name": user.org.name} if user.org_id else None,
        "shift": {"id": user.shift_id, "name": user.shift.shift_vi} if user.shift_id else None,
    }
    if include_knox:
        data["knox_id"] = user.knox_id
    return data


def _user_by_id(user, args: dict) -> dict:
    from apps.accounts.models import User

    row = User.objects.select_related("org", "shift").filter(id=args.get("user_id")).first()
    if row is None:
        return {"error": "Không tìm thấy user"}
    if not _can_view(user, row):
        return {"error": "Bạn không có quyền xem thông tin user này."}
    include_knox = row.id == user.id or has_power(user, [VIEW_PROFILE_POWER])
    return {"user": _user_serialize(row, include_knox=include_knox)}


def _user_by_gen_id(user, args: dict) -> dict:
    from apps.accounts.models import User

    gen_id = str(args.get("gen_id", "")).strip()
    row = User.objects.select_related("org", "shift").filter(gen_id=gen_id).first()
    if row is None:
        return {"error": "Không tìm thấy user có gen_id này"}
    if not _can_view(user, row):
        return {"error": "Bạn không có quyền xem thông tin user này."}
    include_knox = row.id == user.id or has_power(user, [VIEW_PROFILE_POWER])
    return {"user": _user_serialize(row, include_knox=include_knox)}


user_by_id_tool = ToolSpec(
    name="user.get",
    description="Tra cứu user theo id. Chỉ trả thông tin khi cùng org / chính mình / có quyền.",
    input_schema={
        "type": "object",
        "properties": {"user_id": {"type": "integer"}},
        "required": ["user_id"],
        "additionalProperties": False,
    },
    handler=_user_by_id,
)

user_by_gen_id_tool = ToolSpec(
    name="user.get_by_gen_id",
    description="Tra cứu user theo gen_id (mã 8 chữ số). Chỉ trả khi cùng org / chính mình / có quyền.",
    input_schema={
        "type": "object",
        "properties": {"gen_id": {"type": "string"}},
        "required": ["gen_id"],
        "additionalProperties": False,
    },
    handler=_user_by_gen_id,
)