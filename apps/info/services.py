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
                    {"header_id": 100, "header_sort": 1, "header_view": "view_kcs_in", "header_name": "KCS Đầu vào"}
                ],
            }
        ],
    }
"""

from django.db.models import Prefetch

from apps.info.models import GroupHeader, HeaderRegistration, PagesHeader, SystemHeader, UserHeaderRegistration

SUPPORTED_LANGUAGES = ("vi", "en", "kr")

def get_registered_structure(user, language: str) -> list:
	"""Trả về cây group → pages → headers đã đăng ký cho *user* (theo ngôn ngữ)."""
	lang = language if language in SUPPORTED_LANGUAGES else "vi"

	# 1. Header công khai của bộ phận (type=1: không cần đăng ký, status=1: đã duyệt)
	public_ids = HeaderRegistration.objects.filter(
		org_id=user.org_id,
		type=HeaderRegistration.TypeChoices.NO_REGISTRATION,
		status=HeaderRegistration.StatusChoices.APPROVED,
	).values_list("header_id", flat=True)

	# 2. Header đăng ký riêng cho user (status=1: đã duyệt)
	private_ids = UserHeaderRegistration.objects.filter(
		registered_by=user,
		status=UserHeaderRegistration.StatusChoices.APPROVED,
	).values_list("header_registration__header_id", flat=True)

	header_ids = list(dict.fromkeys(list(public_ids) + list(private_ids)))
	if not header_ids:
		return []

	# 3. Dựng cây 3 cấp: Group (is_use) → Pages (is_use) → SystemHeaders (is_use + đã đăng ký)
	groups = GroupHeader.objects.filter(is_use=True).prefetch_related(
		Prefetch(
			"pages",
			queryset=PagesHeader.objects.filter(is_use=True).prefetch_related(
				Prefetch(
					"system_headers",
					queryset=SystemHeader.objects.filter(is_use=True, id__in=header_ids).order_by("sort"),
				)
			),
		)
	)

	structure = []
	for group in groups:
		group_pages = []
		for page in group.pages.all():
			page_headers = [
				{
					"header_id": header.id,
					"header_sort": header.sort,
					"header_view": getattr(header, f"view_{lang}"),
					"header_name": getattr(header, f"header_{lang}"),
				}
				for header in page.system_headers.all()
			]
			if not page_headers:
				continue
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