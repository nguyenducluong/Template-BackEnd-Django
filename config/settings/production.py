from .base import *  # noqa

DEBUG = False

SECURE_SSL_REDIRECT = True
# Django sits behind nginx/XAMPP-Apache reverse proxy which terminates TLS.
# Tell Django to trust the X-Forwarded-Proto header so is_secure() is correct
# and SECURE_SSL_REDIRECT doesn't cause a redirect loop behind the proxy.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Sentry — optional dependency. Initialization is skipped when the package
# is not installed or no SENTRY_DSN is configured, so the app still boots
# (without error tracking) instead of crashing at import time.
try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    _SENTRY_AVAILABLE = True
except ImportError:
    _SENTRY_AVAILABLE = False

if _SENTRY_AVAILABLE and env("SENTRY_DSN", default=None):  # noqa
    sentry_sdk.init(
        dsn=env("SENTRY_DSN"),  # noqa
        integrations=[DjangoIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.2),  # noqa
        send_default_pii=True,
        environment="production",
    )
elif env("SENTRY_DSN", default=None):  # noqa
    import logging

    logging.getLogger(__name__).warning(
        "SENTRY_DSN is configured but sentry-sdk is not installed — "
        "run `pip install -r requirements/prod.txt` to enable error tracking."
    )

# NOTE: uses psycopg2 (no psycopg3 pool support). Keep CONN_MAX_AGE for
# persistent connections instead.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)  # noqa

LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa