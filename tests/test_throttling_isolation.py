"""Test rate-limit auth: login và register phải dùng bucket RIÊNG.

Bug gốc: `LoginRateThrottle` và `RegisterRateThrottle` cùng kế thừa
`get_cache_key` trả về `throttle:auth:<ip>` ⇒ CHUNG MỘT bucket. Người dùng
đăng ký 3 lần sẽ bị chặn login cả giờ (và ngược lại), dù IP hoàn toàn hợp lệ.
"""

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase

from libs.auth.throttling import LoginRateThrottle, RegisterRateThrottle


class ThrottleBucketIsolationTests(SimpleTestCase):
	def setUp(self):
		cache.clear()
		self.factory = RequestFactory()
		self.request = self.factory.post("/accounts/auth/login")

	def test_login_and_register_use_different_cache_keys(self):
		"""Ràng buộc chốt hồi quy — 2 lớp throttle không được dùng chung key."""
		login_key = LoginRateThrottle().get_cache_key(self.request, None)
		register_key = RegisterRateThrottle().get_cache_key(self.request, None)
		self.assertNotEqual(login_key, register_key)

	def test_register_attempts_do_not_block_login(self):
		"""Kịch bản gây lỗi trước đây: 3 lần đăng ký → login bị throttle oan."""
		register = RegisterRateThrottle()
		for _ in range(3):
			self.assertTrue(register.allow_request(self.request, None))
		# Bucket login phải còn trống hoàn toàn.
		self.assertTrue(LoginRateThrottle().allow_request(self.request, None))

	def test_login_attempts_do_not_block_register(self):
		login = LoginRateThrottle()
		for _ in range(5):
			self.assertTrue(login.allow_request(self.request, None))
		self.assertTrue(RegisterRateThrottle().allow_request(self.request, None))

	def test_login_still_blocks_after_its_own_limit(self):
		"""Throttle login vẫn phải hoạt động đúng sau khi tách bucket."""
		login = LoginRateThrottle()
		allowed = [login.allow_request(self.request, None) for _ in range(6)]
		self.assertEqual(allowed, [True] * 5 + [False])

	def test_register_still_blocks_after_its_own_limit(self):
		register = RegisterRateThrottle()
		allowed = [register.allow_request(self.request, None) for _ in range(4)]
		self.assertEqual(allowed, [True] * 3 + [False])

	def test_limit_is_per_ip(self):
		"""IP khác nhau phải có bucket riêng."""
		other = self.factory.post("/accounts/auth/login", REMOTE_ADDR="10.0.0.9")
		login = LoginRateThrottle()
		for _ in range(5):
			self.assertTrue(login.allow_request(self.request, None))
		self.assertTrue(login.allow_request(other, None))


class RefreshThrottleScopeTests(SimpleTestCase):
	def test_refresh_has_its_own_scope_and_rate(self):
		"""Refresh tách khỏi `auth` vì được gọi tự động nhiều lần/ngày."""
		from django.conf import settings

		from apps.accounts.views import RefreshTokenView

		self.assertEqual(RefreshTokenView.throttle_scope, "auth_refresh")
		self.assertIn("auth_refresh", settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"])