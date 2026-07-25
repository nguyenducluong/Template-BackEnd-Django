"""Quick E2E verify: login/refresh/me return joined org + shift data (encrypted, production)."""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DJANGO_ENV"] = "production"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as ap, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from django.test import Client

c = Client(secure=True)
ck = rsa.generate_private_key(65537, 2048)
pub = ck.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()
hs = json.loads(
    c.post("/api/v1/crypto/handshake/", data=json.dumps({"public_key": pub}),
           content_type="application/json", secure=True).content
)["data"]
sess = ck.decrypt(
    base64.b64decode(hs["key"]),
    ap.OAEP(mgf=ap.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
)


def enc_req(obj):
    n = os.urandom(12)
    return json.dumps({
        "payload": base64.b64encode(AESGCM(sess).encrypt(n, obj, None)).decode(),
        "nonce": base64.b64encode(n).decode(),
    })


def dec_resp(raw):
    e = json.loads(raw)
    return AESGCM(sess).decrypt(base64.b64decode(e["nonce"]), base64.b64decode(e["payload"]), None)


n = os.urandom(12)
r = c.post("/api/v1/accounts/auth/login/", data=enc_req(json.dumps({"account": "18764398", "password": "Luongka97*"}).encode()),
           content_type="application/encrypted+json", HTTP_X_SESSION_ID=hs["session_id"], secure=True)
print("login status:", r.status_code)
if r.status_code != 200:
    print("ERROR:", dec_resp(r.content))
resp = json.loads(dec_resp(r.content))
user = resp["user"]
print(json.dumps(user, ensure_ascii=False, indent=2))
assert user["org_full_path"] == "1.2.4.22."
assert user["org_full_name"] == "SET QC Team => IQC G => IQC 2P => Incoming MEC"
assert user["shift_en"] == "Shift 2A1"

access = resp["access"]
r2 = c.get("/api/v1/accounts/auth/me/", HTTP_AUTHORIZATION="Bearer " + access, secure=True)
me = json.loads(r2.content)
print("me:", r2.status_code, "| org_full_name:", me["org_full_name"], "| shift:", me["shift_vi"])
assert me["org_full_path"] == "1.2.4.22."

r3 = c.post("/api/v1/accounts/auth/refresh/", data=enc_req(json.dumps({"refresh": resp["refresh"]}).encode()),
            content_type="application/encrypted+json", HTTP_X_SESSION_ID=hs["session_id"], secure=True)
ref = json.loads(dec_resp(r3.content))
print("refresh:", r3.status_code, "| org_full_path:", ref["user"]["org_full_path"])
assert ref["user"]["org_id"] == 22

print("\nJOIN DATA E2E PASSED (login / me / refresh all include org + shift)")
