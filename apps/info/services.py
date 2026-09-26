"""
Service lấy cấu trúc header đã đăng ký của user — port từ Laravel
``app/Services/Default/GetSystemsService.php``.

Logic:
    1. Header CÔNG KHAI của bộ phận: HeaderRegistration (org của user,
       type=1 "không cần đăng ký", status=1 "đã duyệt").
    2. Header RIÊNG của user: UserHeaderRegistration (registered_by=user,
       status=1 "đã duyệt").
    3. Gộp id (unique) → lọc cây GroupHeader → PagesHeader → SystemHeader
       (is_use=True, id nằm trong danh sách đã đăng ký) → lọc nhóm/page rỗng.

Shape trả về giữ đúng Laravel để frontend STD parse không đổi:
    {
        "group_id": 1, "group_sort": 1, "group_name": "KCS",
        "group_pages": [
            {
                "page_id": 10, "page_sort": 1, "page_name": "Kiểm tra",
                "page_headers": [
                    {"header_id": 10000, "header_sort": 1, "header_view": "view_kcs_in", "header_name": "KCS Đầu vào"}
                ]
            }
        ]
    }

Tối ưu:
    - Cây 3 cấp dựng bằng ĐÚNG 3 query nhờ ``prefetch_related`` +
      ``_build_structure`` chỉ đọc ``.all()`` trên cache prefetch (KHÔNG gọi
      ``.filter()`` lại trên related manager — thao tác đó phá cache prefetch và
      gây N+1 như bản cũ của ``apps/info/views.py``).
    - Danh sách header được phép của user lấy từ cache quyền T1
      (``apps.info.permissions.get_user_permitted_header_ids``).
    - Cây menu được cache theo (user, ngôn ngữ); vô hiệu hoá bằng cách tăng
      "version" (``bump_structure_version``) — không cần quét/xoá từng key nên
      hoạt động với mọi cache backend.
"""

from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch

from apps.info.models import GroupHeader, PagesHeader, SystemHeader
from apps.info.permissions import get_user_permitted_header_ids

SUPPORTED_LANGUAGES = ("vi", "en", "kr")

# Header "Init System" luôn được chèn đầu mỗi page của MENU USER (giữ đúng
# shape Laravel cũ; không xuất hiện ở chế độ xem đầy đủ cho quản trị).
INIT_SYSTEM_HEADER = {
    "header_id": 10000,
    "header_sort": 0,
    "header_view": "Init System",
    "header_name": "Init System",
}

# ---- Cache cây menu -------------------------------------------------------
STRUCTURE_VERSION_KEY = "info:structure:version"
STRUCTURE_CACHE_KEY = "info:structure:v{version}:{user_id}:{lang}"
STRUCTURE_CACHE_TTL = 300  # giây — override bằng settings.INFO_STRUCTURE_CACHE_TTL


def _cache_ttl() -> int:
    return getattr(settings, "INFO_STRUCTURE_CACHE_TTL", STRUCTURE_CACHE_TTL)


def _structure_version() -> int:
    """Version hiện tại của cache cây menu (tự khởi tạo = 1)."""
    version = cache.get(STRUCTURE_VERSION_KEY)
    if version is None:
        cache.add(STRUCTURE_VERSION_KEY, 1, timeout=None)
        version = cache.get(STRUCTURE_VERSION_KEY) or 1
    return int(version)


def bump_structure_version() -> None:
    """Vô hiệu hoá toàn bộ cache cây menu (gọi khi Group/Pages/SystemHeader đổi)."""
    try:
        cache.incr(STRUCTURE_VERSION_KEY)
    except ValueError:
        # Key chưa tồn tại / vừa hết hạn → khởi tạo lại
        cache.set(STRUCTURE_VERSION_KEY, 1, timeout=None)


# Tên dễ đọc khi gọi từ signals / dispatcher.
invalidate_structure_cache = bump_structure_version


def _groups_queryset(header_ids=None):
    """Query cây 3 cấp đã tối ưu (3 query, không N+1).

    ``order_by`` đặt TRÊN queryset của Prefetch để thứ tự lấy từ cache prefetch
    (không phát sinh query mới cho mỗi group/page).
    """
    headers = SystemHeader.objects.filter(is_use=True).order_by("sort", "id")
    if header_ids is not None:
        headers = headers.filter(id__in=header_ids)

    pages = (
        PagesHeader.objects.filter(is_use=True)
        .order_by("sort", "id")
        .prefetch_related(Prefetch("system_headers", queryset=headers))
    )
    return (
        GroupHeader.objects.filter(is_use=True)
        .order_by("sort", "id")
        .prefetch_related(Prefetch("pages", queryset=pages))
    )


def _build_structure(groups, lang: str, prepend_init: bool = False) -> list:
    """Dựng list group → pages → headers từ queryset ĐÃ prefetch."""
    structure = []
    for group in groups:
        group_pages = []
        for page in group.pages.all():  # đọc cache prefetch — không query thêm
            page_headers = [
                {
                    "header_id": header.id,
                    "header_sort": header.sort,
                    "header_view": getattr(header, f"view_{lang}"),
                    "header_name": getattr(header, f"header_{lang}"),
                }
                for header in page.system_headers.all()  # đọc cache prefetch
            ]
            if not page_headers:
                continue
            if prepend_init:
                page_headers = [dict(INIT_SYSTEM_HEADER), *page_headers]
            group_pages.append(
                {
                    "page_id": page.id,
                    "page_sort": page.sort,
                    "page_name": getattr(page, f"page_{lang}"),
                    "page_headers": page_headers,
                }
            )
        if not group_pages:
            continue
        structure.append(
            {
                "group_id": group.id,
                "group_sort": group.sort,
                "group_name": getattr(group, f"group_{lang}"),
                "group_pages": group_pages,
            }
        )
    return structure


def get_registered_structure(user, language: str, use_cache: bool = True) -> list:
    """Trả về cây group → pages → headers đã đăng ký cho *user* (theo ngôn ngữ).

    Kết quả được cache theo (user, ngôn ngữ) — ``use_cache=False`` khi cần dữ
    liệu tươi ngay (test / ngay sau khi ghi cấu hình).
    """
    lang = language if language in SUPPORTED_LANGUAGES else "vi"
    if user is None or not getattr(user, "id", None):
        return []

    cache_key = STRUCTURE_CACHE_KEY.format(version=_structure_version(), user_id=user.id, lang=lang)
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    # Danh sách header user được phép — đã có cache riêng theo user (quyền T1).
    header_ids = get_user_permitted_header_ids(user)
    if not header_ids:
        structure = []
    else:
        structure = _build_structure(_groups_queryset(header_ids), lang, prepend_init=True)

    if use_cache:
        cache.set(cache_key, structure, _cache_ttl())
    return structure


def get_full_structure(language: str) -> list:
    """Cây ĐẦY ĐỦ (mọi header ``is_use=True``) — chỉ dùng cho quản trị.

    Không chèn header "Init System" và KHÔNG lọc theo quyền T1 ⇒ caller phải
    kiểm tra quyền ghi cấu hình trước khi trả dữ liệu này.
    """
    lang = language if language in SUPPORTED_LANGUAGES else "vi"
    return _build_structure(_groups_queryset(), lang, prepend_init=False)

