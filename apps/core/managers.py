from django.db import models


class BaseManager(models.Manager):
    """Base manager with common query methods."""

    def get_by_id(self, id):
        """Get object by UUID id."""
        try:
            return self.get(id=id)
        except self.model.DoesNotExist:
            return None