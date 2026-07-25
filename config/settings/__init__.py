import os

environment = os.getenv("DJANGO_ENV", "development")

if environment == "production":
    from .production import *  # noqa
elif environment == "staging":
    from .staging import *  # noqa
else:
    from .development import *  # noqa