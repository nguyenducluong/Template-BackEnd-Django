import os
import sys
import asyncio
from pathlib import Path

# Allow running directly: `python tests/smoke_ws.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_ENV"] = "development"

import django
django.setup()

from apps.accounts.models import User
from apps.info.models import Organization, Shift
from libs.auth.jwt_utils import generate_tokens
from libs.auth.jwt_middleware import JWTAuthMiddleware

org, _ = Organization.objects.get_or_create(id=999, defaults={"name": "Test Org", "sort": 1, "is_use": True})
shift, _ = Shift.objects.get_or_create(id=999, defaults={"shift_vi": "Test", "shift_en": "Test", "shift_kr": "Test"})

User.objects.filter(gen_id="87654321").delete()
user = User.objects.create(
    gen_id="87654321", knox_id="wstest", full_name="WS Test",
    org=org, shift=shift, status=User.StatusChoices.APPROVED,
)
user.set_password("TestPass123")
user.save()

access = generate_tokens(user)["access"]
captured = {}

def make_inner(key):
    async def inner(scope, receive, send):
        captured[key] = scope.get("user")
    return inner

async def receive():
    return {}

async def send(message):
    pass

loop = asyncio.new_event_loop()

scope = {"type": "websocket", "headers": [(b"authorization", ("Bearer " + access).encode())], "query_string": b""}
loop.run_until_complete(JWTAuthMiddleware(make_inner("h"))(scope, receive, send))
assert getattr(captured["h"], "gen_id", None) == user.gen_id
print("Header auth OK")

scope2 = {"type": "websocket", "headers": [], "query_string": b""}
loop.run_until_complete(JWTAuthMiddleware(make_inner("a"))(scope2, receive, send))
assert getattr(captured["a"], "is_authenticated", False) is False
print("Anonymous fallback OK")

scope3 = {"type": "websocket", "headers": [], "query_string": ("token=" + access).encode()}
loop.run_until_complete(JWTAuthMiddleware(make_inner("q"))(scope3, receive, send))
assert getattr(captured["q"], "gen_id", None) == user.gen_id
print("Query-string auth OK")

scope4 = {"type": "websocket", "headers": [(b"authorization", b"Bearer invalid.token.here")], "query_string": b""}
loop.run_until_complete(JWTAuthMiddleware(make_inner("i"))(scope4, receive, send))
assert getattr(captured["i"], "is_authenticated", False) is False
print("Invalid token -> anonymous OK")

user.delete()
print()
print("=== WEBSOCKET JWT MIDDLEWARE TESTS PASSED ===")