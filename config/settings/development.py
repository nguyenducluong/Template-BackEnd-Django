from .base import *  # noqa

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS += [  # noqa
    "django_extensions",
    "debug_toolbar",
]

MIDDLEWARE += [  # noqa
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

INTERNAL_IPS = [
    "127.0.0.1",
]

# Database: kế thừa PostgreSQL từ base settings (config qua .env)
USE_PGVECTOR = env.bool("USE_PGVECTOR", default=True)  # noqa

CACHES["default"]["BACKEND"] = "django.core.cache.backends.locmem.LocMemCache"  # noqa

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] = (  # noqa
    "rest_framework.renderers.JSONRenderer",
    "rest_framework.renderers.BrowsableAPIRenderer",
)

CORS_ALLOW_ALL_ORIGINS = True

LOGGING["loggers"]["django"]["level"] = "DEBUG"  # noqa