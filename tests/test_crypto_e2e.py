"""E2E test: handshake + encrypted request/response (run with DJANGO_ENV=production)."""
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

from django.conf import settings
from django.test import Client

print("ENABLE_API_ENCRYPTION:", settings.ENABLE_API_ENCRYPTION)
assert settings.ENABLE_API_ENCRYPTION is True, "encryption must be ON in production"

# --- client keypair (server-side generated just for the test) ---
ck = rsa.generate_private_key(public_exponent=65537, key_size=2048)
client_pub_pem = ck.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()

c = Client(secure=True)  # https scheme — SECURE_SSL_REDIRECT is on in production settings

# --- handshake ---
r = c.post("/api/v1/crypto/handshake/", data=json.dumps({"public_key": client_pub_pem}), content_type="application/json", secure=True)
print("handshake:", r.status_code)
assert r.status_code == 200, r.content
hs = json.loads(r.content)["data"]

# unwrap session AES key with client private key
sess_key = ck.decrypt(
    base64.b64decode(hs["key"]),
    ap.OAEP(mgf=ap.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
)
assert len(sess_key) == 32
probe = AESGCM(sess_key).decrypt(base64.b64decode(hs["nonce"]), base64.b64decode(hs["payload"]), None)
assert b"AES-256-GCM" in probe
print("session key unwrapped OK, probe:", probe)

# --- encrypted request to login (real endpoint, real DB) ---
body = json.dumps({"account": "18764398", "password": "Luongka97*"}).encode()
nonce = os.urandom(12)
ct = AESGCM(sess_key).encrypt(nonce, body, None)
r = c.post(
    "/api/v1/accounts/auth/login/",
    data=json.dumps({"payload": base64.b64encode(ct).decode(), "nonce": base64.b64encode(nonce).decode()}),
    content_type="application/encrypted+json",
    HTTP_X_SESSION_ID=hs["session_id"],
    secure=True,
)
print("login (encrypted):", r.status_code, r.headers.get("Content-Type"))
assert r.status_code == 200, r.content
assert r.headers["Content-Type"].startswith("application/encrypted+json"), "response must be encrypted"
resp = json.loads(r.content)
plain = AESGCM(sess_key).decrypt(base64.b64decode(resp["nonce"]), base64.b64decode(resp["payload"]), None)
data = json.loads(plain)
print("decrypted response keys:", sorted(data.keys()))
assert data["user"]["gen_id"] == "18764398" and data["access"]

# --- plaintext request also works (backward compat) ---
r2 = c.post("/api/v1/accounts/auth/login/", data=body, content_type="application/json", secure=True)
print("login (plaintext):", r2.status_code, r2.headers.get("Content-Type"))
assert r2.status_code == 200 and not r2.headers["Content-Type"].startswith("application/encrypted")

# --- tampered payload rejected ---
bad = {"payload": base64.b64encode(b"xxxx").decode(), "nonce": base64.b64encode(nonce).decode()}
r3 = c.post("/api/v1/accounts/auth/login/", data=json.dumps(bad), content_type="application/encrypted+json",
            HTTP_X_SESSION_ID=hs["session_id"], secure=True)
print("tampered:", r3.status_code, json.loads(r3.content)["message"])
assert r3.status_code == 400

# --- invalid session rejected ---
r4 = c.post("/api/v1/accounts/auth/login/", data=json.dumps({"payload": "AA==", "nonce": base64.b64encode(nonce).decode()}),
            content_type="application/encrypted+json", HTTP_X_SESSION_ID="deadbeef", secure=True)
assert r4.status_code == 400

# --- large payload (tests AES for >RSA limit) ---
big = json.dumps({"account": "18764398", "password": "Luongka97*", "pad": "x" * 100000}).encode()
n2 = os.urandom(12)
ct2 = AESGCM(sess_key).encrypt(n2, big, None)
r5 = c.post("/api/v1/accounts/auth/login/",
            data=json.dumps({"payload": base64.b64encode(ct2).decode(), "nonce": base64.b64encode(n2).decode()}),
            content_type="application/encrypted+json", HTTP_X_SESSION_ID=hs["session_id"], secure=True)
print("large payload (~100KB encrypted):", r5.status_code)
assert r5.status_code == 200

print("\nALL ENCRYPTION E2E TESTS PASSED (DJANGO_ENV=production)")
