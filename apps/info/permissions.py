"""
Quyền T1 (theo header) cho các endpoint hệ thống — ROADMAP P1.5.

Nguồn danh sách header mà user được phép truy cập — đúng pattern
``apps.info.services.get_registered_structure``:

    1. Header CÔNG KHAI của bộ phận: ``HeaderRegistration``
       (org = org của user, type = NO_REGISTRATION, status = APPROVED).
    2. Header RIÊNG của user: ``UserHeaderRegistration``
       (registered_by = user, status = APPROVED).

Kết quả được cache theo user:

    key   ``systems:perm:{user_id}``
    TTL   ``SYSTEMS_PERM_CACHE_TTL`` (mặc định 60 giây)

``HasHeaderPermission`` là DRF permission class — trả 403 khi user không có
quyền truy cập header của request. Header cần kiểm tra lấy theo thứ tự:

    1. ``view.header_id`` — view khai header cố định (HeaderNDetailsView).
    2. ``request.data["header_id"]`` — dispatcher ``systems/init_data``.

Header demo (``apps.systems.views.DEMO_HEADER_IDS``) được bypass — chỉ cần
đăng nhập, không tra HeaderRegistration/UserHeaderRegistration trong DB.
Header thật kiểm tra DB như cũ.
"""

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext as _
from rest_framework.permissions import BasePermission

from apps.info.models import HeaderRegistration, UserHeaderRegistration

# Header demo — bypass DB/quyền: chỉ cần đăng nhập, không cần SystemHeader /
# HeaderRegistration / SystemPower trong DB. Header thật không thuộc tập này.
# Đặt tại đây (thay vì apps.systems.views) để tránh import vòng
# (views.py đã import HasHeaderPermission từ module này).
DEMO_HEADER_IDS = frozenset({10000})

# Cache key của danh sách header hợp lệ theo user — ROADMAP P1.5.
PERM_CACHE_KEY = "systems:perm:{user_id}"

# TTL mặc định (giây) — override bằng settings.SYSTEMS_PERM_CACHE_TTL.
PERM_CACHE_TTL = 60


def get_perm_cache_key(user_id) -> str:
    """Khóa cache danh sách header hợp lệ của user."""
    return PERM_CACHE_KEY.format(user_id=user_id)


def _fetch_permitted_header_ids(user) -> list:
    """Truy vấn DB trực tiếp (không qua cache) — tách riêng để unit test patch."""

    # 1. Header công khai của bộ phận: type=1 (không cần đăng ký), status=1 (đã duyệt)
    org_id = getattr(user, "org_id", None)
    if org_id:
        public_ids = HeaderRegistration.objects.filter(
            org_id=org_id,
            type=HeaderRegistration.TypeChoices.NO_REGISTRATION,
            status=HeaderRegistration.StatusChoices.APPROVED,
        ).values_list("header_id", flat=True)
    else:
        public_ids = []

    # 2. Header đăng ký riêng của user: status=1 (đã duyệt)
    private_ids = UserHeaderRegistration.objects.filter(
        registered_by_id=user.id,
        status=UserHeaderRegistration.StatusChoices.APPROVED,
    ).values_list("header_registration__header_id", flat=True)

    # 3. Hợp nhất id (unique, tăng dần) — cùng logic với get_registered_structure
    return sorted(set(public_ids) | set(private_ids))


def get_user_permitted_header_ids(user) -> list:
    """Danh sách ``SystemHeader.id`` mà user được phép truy cập (quyền T1).

    Có cache theo user (key ``systems:perm:{user_id}``); kết quả rỗng cũng được
    cache để tránh đấm query mỗi request.
    """
    if not user or not getattr(user, "id", None):
        return []

    key = get_perm_cache_key(user.id)
    cached = cache.get(key)
    if cached is not None:
        return cached

    header_ids = _fetch_permitted_header_ids(user)
    cache.set(key, header_ids, getattr(settings, "SYSTEMS_PERM_CACHE_TTL", PERM_CACHE_TTL))
    return header_ids


def user_has_header_permission(user, header_id) -> bool:
	"""True nếu *user* được phép truy cập *header_id* (quyền T1).

	Header demo (``DEMO_HEADER_IDS``) được bypass — chỉ cần user hợp lệ,
	không tra HeaderRegistration/UserHeaderRegistration trong DB.
	"""
	try:
		header_id = int(header_id)
	except (TypeError, ValueError):
		return False
	if header_id in DEMO_HEADER_IDS:
		return user is not None and getattr(user, 'id', None) is not None
	return header_id in get_user_permitted_header_ids(user)


def invalidate_permission_cache(user_id) -> None:
    """Xóa cache quyền của 1 user (gọi khi UserHeaderRegistration thay đổi)."""
    cache.delete(get_perm_cache_key(user_id))


def invalidate_org_permission_cache(org_id) -> None:
    """Xóa cache quyền của mọi user trong *org* (khi HeaderRegistration thay đổi)."""
    if not org_id:
        return
    from apps.accounts.models import User  # tránh import vòng ở lượt import đầu

    user_ids = list(User.objects.filter(org_id=org_id).values_list("id", flat=True))
    if user_ids:
        cache.delete_many([get_perm_cache_key(uid) for uid in user_ids])


class HasHeaderPermission(BasePermission):
    """DRF permission — 403 khi user không có quyền truy cập header của request.

    - View khai ``header_id`` cố định (HeaderNDetailsView) → kiểm tra trực tiếp.
    - Dispatcher ``systems/init_data`` lấy ``header_id`` từ body request.
    - Header demo (``DEMO_HEADER_IDS``) → cho qua nếu đã đăng nhập (bypass DB).
    - Không xác định được ``header_id`` (thiếu / sai kiểu) → cho qua để view tự
      validate và trả 400 đúng contract hiện tại.
    """

    message = _("You do not have permission to access this system header.")

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False

        header_id = getattr(view, "header_id", None)
        if header_id is None:
            data = getattr(request, "data", None)
            # body có thể không phải dict (vd: JSON array) → để view tự validate
            header_id = data.get("header_id") if hasattr(data, "get") else None
        if header_id is None:
            return True  # thiếu header_id → view tự trả 400
        try:
            int(header_id)
        except (TypeError, ValueError):
            return True  # header_id sai kiểu → view tự trả 400
        return user_has_header_permission(user, header_id)
