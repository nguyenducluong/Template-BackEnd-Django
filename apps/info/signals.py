"""
Organization signals for maintaining denormalized hierarchy cache.

When an organization's name or parent changes, update cached_full_path
and cached_full_name for this org and all its descendants.
"""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import HeaderRegistration, Organization, UserHeaderRegistration
from .permissions import invalidate_org_permission_cache, invalidate_permission_cache

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
