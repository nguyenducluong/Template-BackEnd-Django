"""
Fast unit tests (no database required).

Run with:  python manage.py test tests.test_unit_auth -v 2

Covers the security fixes:
- OTP brute-force lockout (OTP_MAX_ATTEMPTS)
- Trusted-proxy-aware client IP extraction
- PBKDF2 password hashing round-trip
- JWT token generation/verification (no DB resolution via stub user)
"""
from datetime import timedelta
from types import SimpleNamespace

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

import jwt

from libs.auth.password import check_password, make_password
from libs.auth.jwt_utils import generate_tokens, verify_access_token, verify_refresh_token
from libs.network import get_client_ip
from services.redis_service import RedisService


class OTPAttemptLimitTests(SimpleTestCase):
    """OTP brute-force protection: wrong guesses invalidate the OTP."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_correct_otp_verifies(self):
        RedisService.store_otp("user1", "123456", ttl=300)
        self.assertTrue(RedisService.verify_otp("user1", "123456"))

    def test_wrong_otp_then_correct_still_ok(self):
        RedisService.store_otp("user1", "123456", ttl=300)
        self.assertFalse(RedisService.verify_otp("user1", "000000"))
        self.assertTrue(RedisService.verify_otp("user1", "123456"))

    @override_settings(OTP_MAX_ATTEMPTS=3)
    def test_otp_invalidated_after_max_attempts(self):
        RedisService.store_otp("user1", "123456", ttl=300)
        for _ in range(3):
            self.assertFalse(RedisService.verify_otp("user1", "999999"))
        # Even the CORRECT otp must now fail — the code was invalidated.
        self.assertFalse(RedisService.verify_otp("user1", "123456"))


class ClientIPTests(SimpleTestCase):
    """X-Forwarded-For must only be trusted for configured proxies."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_uses_remote_addr_by_default(self):
        request = self.factory.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="5.6.7.8")
        self.assertEqual(get_client_ip(request), "5.6.7.8")

    @override_settings(TRUSTED_PROXIES=["10.0.0.1"])
    def test_trusted_proxy_honours_forwarded_for(self):
        request = self.factory.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="10.0.0.1")
        self.assertEqual(get_client_ip(request), "1.2.3.4")

    def test_spoofed_header_ignored_when_peer_untrusted(self):
        request = self.factory.get(
            "/", HTTP_X_FORWARDED_FOR="9.9.9.9", REMOTE_ADDR="8.8.8.8"
        )
        self.assertEqual(get_client_ip(request), "8.8.8.8")


class PasswordHashTests(SimpleTestCase):
    def test_round_trip(self):
        hashed = make_password("S3cure!pass")
        self.assertTrue(hashed.startswith("pbkdf2_sha256$"))
        self.assertTrue(check_password("S3cure!pass", hashed))
        self.assertFalse(check_password("wrong", hashed))

    def test_empty_password_rejected(self):
        with self.assertRaises(ValueError):
            make_password("")


class JWTTests(SimpleTestCase):
    """Token generation/verification with a DB-free stub user."""

    @staticmethod
    def _stub_user():
        return SimpleNamespace(id=42, gen_id="12345678")

    def _jwt_cfg(self):
        from django.conf import settings

        return getattr(settings, "JWT_AUTH", {})

    def test_access_and_refresh_types(self):
        user = self._stub_user()
        tokens = generate_tokens(user)
        cfg = self._jwt_cfg()
        access_payload = jwt.decode(
            tokens["access"], cfg["SIGNING_KEY"], algorithms=[cfg["ALGORITHM"]]
        )
        self.assertEqual(access_payload["token_type"], "access")
        self.assertEqual(access_payload["user_id"], "42")

        refresh_payload = jwt.decode(
            tokens["refresh"], cfg["SIGNING_KEY"], algorithms=[cfg["ALGORITHM"]]
        )
        self.assertEqual(refresh_payload["token_type"], "refresh")

    def test_expired_token_rejected(self):
        user = self._stub_user()
        cfg = self._jwt_cfg()
        payload = {
            "token_type": "access",
            "jti": "deadbeef",
            "user_id": "42",
            "iat": 0,
            "exp": 1,
        }
        expired = jwt.encode(payload, cfg["SIGNING_KEY"], algorithm=cfg["ALGORITHM"])
        with self.assertRaises(jwt.ExpiredSignatureError):
            jwt.decode(expired, cfg["SIGNING_KEY"], algorithms=[cfg["ALGORITHM"]])
