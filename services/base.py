"""
Base service class providing common patterns for all services.
Services encapsulate business logic and abstract away implementation details.
"""
from django.db import transaction


class BaseService:
    """
    Base class for all services.

    Usage:
        class UserService(BaseService):
            model = User

            def create_user(self, data):
                return self.create(data)
    """

    model = None

    def get(self, id):
        """Get a single record by ID."""
        return self.model.objects.get_by_id(id)

    def get_or_none(self, id):
        """Get a record by ID or return None."""
        try:
            return self.model.objects.get(id=id)
        except self.model.DoesNotExist:
            return None

    def list(self, **filters):
        """List records with optional filters."""
        return self.model.objects.filter(**filters)

    @transaction.atomic
    def create(self, **kwargs):
        """Create a new record."""
        return self.model.objects.create(**kwargs)

    @transaction.atomic
    def update(self, instance, **kwargs):
        """Update an existing record."""
        for attr, value in kwargs.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    @transaction.atomic
    def delete(self, instance):
        """Hard delete a record."""
        instance.delete()

    def exists(self, **filters):
        """Check if a record exists."""
        return self.model.objects.filter(**filters).exists()

    def count(self, **filters):
        """Count records matching filters."""
        return self.model.objects.filter(**filters).count()