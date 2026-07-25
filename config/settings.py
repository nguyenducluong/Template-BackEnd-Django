"""
Legacy default settings — NOT the active settings module.

The project uses the settings package at ``config/settings/``.
``config/settings/__init__.py`` dispatches to ``development``,
``staging``, or ``production`` based on the ``DJANGO_ENV`` env var.
"""
