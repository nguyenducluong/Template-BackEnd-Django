"""
Password validation for custom User model.

Phase 1e: enforce strong passwords (min 8 chars + 1 uppercase + 1 number + 1 special char).
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class StrongPasswordValidator:
    """Validate that password meets complexity requirements."""

    MIN_LENGTH = 8
    SPECIAL_CHARS = r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?`~]"

    def validate(self, password, user=None):
        if len(password) < self.MIN_LENGTH:
            raise ValidationError(
                _("Password must be at least %(min_length)d characters."),
                code="password_too_short",
                params={"min_length": self.MIN_LENGTH},
            )
        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                _("Password must contain at least one uppercase letter."),
                code="password_no_uppercase",
            )
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                _("Password must contain at least one lowercase letter."),
                code="password_no_lowercase",
            )
        if not re.search(r"\d", password):
            raise ValidationError(
                _("Password must contain at least one digit."),
                code="password_no_digit",
            )
        if not re.search(self.SPECIAL_CHARS, password):
            raise ValidationError(
                _("Password must contain at least one special character."),
                code="password_no_special",
            )

    def get_help_text(self):
        return _(
            "Password must be at least 8 characters with at least one "
            "uppercase letter, one lowercase letter, one digit, and one special character."
        )
