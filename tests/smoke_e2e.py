import os
import sys
from pathlib import Path

# Allow running directly: `python tests/smoke_e2e.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["DJANGO_ENV"] = "development"

import django
django.setup()

from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.info.models import Organization, Shift

org, _ = Organization.objects.get_or_create(id=999, defaults={"name": "Test Org", "sort": 1, "is_use": True})
shift, _ = Shift.objects.get_or_create(id=999, defaults={"shift_vi": "Test", "shift_en": "Test", "shift_kr": "Test"})

User.objects.filter(gen_id="12345678").delete()
user = User.objects.create(
    gen_id="12345678", knox_id="test", full_name="DRF Test",
    org=org, shift=shift, status=User.StatusChoices.APPROVED,
)
user.set_password("SecurePass123")
user.save()

client = APIClient()

# 1. Login (qua gen_id)
resp = client.post("/api/v1/accounts/auth/login/", {
    "account": "12345678", "password": "SecurePass123",
}, format="json")
assert resp.status_code == 200, resp.data
access, refresh = resp.data["access"], resp.data["refresh"]
print("Login OK")

# 2. GET /me/
client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
resp = client.get("/api/v1/accounts/auth/me/")
assert resp.status_code == 200 and resp.data["gen_id"] == user.gen_id
print("GET /me/ OK")

# 3. Update profile
resp = client.post("/api/v1/accounts/auth/me/", {"full_name": "Updated Name"}, format="json")
assert resp.status_code == 200 and resp.data["full_name"] == "Updated Name"
print("POST /me/ OK")

# 4. Change password
resp = client.post("/api/v1/accounts/auth/change-password/", {
    "old_password": "SecurePass123", "new_password": "NewSecurePass456",
}, format="json")
assert resp.status_code == 200, resp.data
print("change-password OK")

# 5. Refresh with rotation
resp = client.post("/api/v1/accounts/auth/refresh/", {"refresh": refresh}, format="json")
assert resp.status_code == 200, resp.data
new_access, new_refresh = resp.data["access"], resp.data["refresh"]
client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
assert client.get("/api/v1/accounts/auth/me/").status_code == 200
print("refresh + rotation OK")

# 6. Logout blacklists refresh token
client.credentials()
resp = client.post("/api/v1/accounts/auth/logout/", {"refresh": new_refresh}, format="json")
assert resp.status_code == 200
resp = client.post("/api/v1/accounts/auth/refresh/", {"refresh": new_refresh}, format="json")
assert resp.status_code == 400
print("logout + blacklist OK")

# 7. Unauthorized -> 401
assert client.get("/api/v1/accounts/auth/me/").status_code == 401
assert client.post("/api/v1/face/register/").status_code == 401
assert client.post("/api/v1/face/search/").status_code == 401
assert client.post("/api/v1/face/verify/").status_code == 401
print("401 for unauthenticated access OK (accounts + face)")

user.delete()
print()
print("=== E2E SMOKE TEST PASSED ===")