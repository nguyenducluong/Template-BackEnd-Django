"""
Signals của app info:

1. Cache cây phân cấp Organization (``cached_full_path``/``cached_full_name``).
2. Cache quyền T1 theo user (``systems:perm:{user_id}``) — ROADMAP P1.5.
3. Cache cây menu header (``info:structure:*``) — vô hiệu hoá khi Group/Pages/
   SystemHeader hoặc đăng ký header thay đổi.
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import (
    GroupHeader,
    HeaderRegistration,
    Organization,
    PagesHeader,
    SystemHeader,
    UserHeaderRegistration,
)
from .permissions import invalidate_org_permission_cache, invalidate_permission_cache
from .services import invalidate_structure_cache

logger = logging.getLogger(__name__)


def _refresh_org_hierarchy(org: Organization):
    """Recompute and save cached hierarchy for a single org."""
    path, name = org._compute_hierarchy()
    Organization.objects.filter(pk=org.pk).update(
        cached_full_path=path,
        cached_full_name=name,
    )


def _refresh_descendants(org: Organization):
    """Recompute cached hierarchy for org and all its descendants."""
    _refresh_org_hierarchy(org)
    for child in org.children.all():
        _refresh_descendants(child)


@receiver(post_save, sender=Organization)
def update_hierarchy_cache(sender, instance: Organization, **kwargs):
    """Update cached hierarchy when an org is saved."""
    try:
        _refresh_descendants(instance)
    except Exception as e:
        # Don't break the save if cache update fails
        logger.warning("Failed to update org hierarchy cache: %s", e)


# ---------------------------------------------------------------------------
# Cache quyền T1 (`systems:perm:{user_id}`) — ROADMAP P1.5
# ---------------------------------------------------------------------------

@receiver([post_save, post_delete], sender=HeaderRegistration)
def invalidate_header_registration_cache(sender, instance: HeaderRegistration, **kwargs):
    """HeaderRegistration đổi → xóa cache quyền của mọi user trong org."""
    try:
        invalidate_org_permission_cache(instance.org_id)
    except Exception as e:
        # Không để lỗi cache làm hỏng save/delete
        logger.warning("Failed to invalidate header perm cache for org %s: %s", instance.org_id, e)


@receiver([post_save, post_delete], sender=UserHeaderRegistration)
def invalidate_user_header_registration_cache(sender, instance: UserHeaderRegistration, **kwargs):
    """UserHeaderRegistration đổi → xóa cache quyền của user đó."""
    try:
        invalidate_permission_cache(instance.registered_by_id)
    except Exception as e:
        logger.warning("Failed to invalidate user perm cache for user %s: %s", instance.registered_by_id, e)


# ---------------------------------------------------------------------------
# Cache cây menu header (`info:structure:*`) — tối ưu hệ thống
#
# Cây menu được cache theo (user, ngôn ngữ). Mọi thay đổi về cấu trúc
# (Group/Pages/SystemHeader) hoặc về đăng ký header đều phải vô hiệu hoá cache,
# nếu không user sẽ thấy menu cũ tới 5 phút (INFO_STRUCTURE_CACHE_TTL).
# ---------------------------------------------------------------------------

@receiver([post_save, post_delete], sender=GroupHeader)
@receiver([post_save, post_delete], sender=PagesHeader)
@receiver([post_save, post_delete], sender=SystemHeader)
def invalidate_header_structure_cache(sender, instance, **kwargs):
    """Group/Pages/SystemHeader đổi → vô hiệu hoá cache cây menu của mọi user."""
    try:
        invalidate_structure_cache()
    except Exception as e:
        logger.warning("Failed to invalidate header structure cache: %s", e)


@receiver([post_save, post_delete], sender=HeaderRegistration)
@receiver([post_save, post_delete], sender=UserHeaderRegistration)
def invalidate_structure_cache_on_registration_change(sender, instance, **kwargs):
    """Đăng ký header đổi → cây menu của user liên quan cũng phải dựng lại."""
    try:
        invalidate_structure_cache()
    except Exception as e:
        logger.warning("Failed to invalidate header structure cache: %s", e)
