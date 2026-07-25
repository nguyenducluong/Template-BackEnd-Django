from .production import *  # noqa

DEBUG = True

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["*"])  # noqa

SENTRY_ENVIRONMENT = "staging"  # noqa