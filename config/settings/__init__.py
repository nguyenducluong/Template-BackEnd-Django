import os

environment = os.getenv("DJANGO_ENV", "development")

if environment == "production":
    from .production import *  # noqa
elif environment == "staging":
    from .staging import *  # noqa
elif environment == "test":
    # Chạy test: gộp mọi model về schema `public` — xem giải thích dài trong
    # `test.py`. Không có nhánh này thì Django test runner không tạo được bảng
    # của các schema riêng ⇒ "relation _0010_user does not exist".
    from .test import *  # noqa
else:
    from .development import *  # noqa