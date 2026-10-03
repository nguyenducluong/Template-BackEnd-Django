"""Test cho Refresh Token OPAQUE + Token Family + Rotation + Reuse Detection.

Run:  python manage.py test tests.test_refresh_token_family -v 2

Phủ đúng các INVARIANT của spec §79 mà phần backend đảm nhiệm:
  INVARIANT 1  — mỗi token chỉ dùng thành công 1 lần
  INVARIANT 2  — token đã revoked không cấp được token mới
  INVARIANT 3  — reuse token đã xoay ⇒ kích hoạt thu hồi cả family
  INVARIANT 4  — không lưu plaintext refresh token trong DB
  INVARIANT 7  — một user có nhiều phiên độc lập
  INVARIANT 8  — thu hồi 1 phiên không ảnh hưởng phiên khác
  INVARIANT 11 — race condition không sinh 2 token hợp lệ từ 1 token gốc
"""
import threading
import uuid
from datetime import timedelta


from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import RefreshTokenSession, User
from libs.auth import refresh_tokens as rt


def make_user(gen_id, full_name="Test User"):
    """Tạo user tối đa đủ cho luồng refresh.

    `User` của dự án là custom: KHÔNG kế thừa AbstractBaseUser nên không có
    `username`/`is_active`/`password` kiểu Django mặc định.
      - định danh đăng nhập: `gen_id` (8 chữ số)
      - `is_active` là PROPERTY suy ra từ `status == APPROVED` ⇒ phải set
        `status`, không gán `is_active`
      - mật khẩu đặt qua `set_password()` (PBKDF2)
      - `org`/`shift` là FK NOT NULL ⇒ phải tạo trước
    """
    from apps.info.models import Organization, Shift

    org = Organization.objects.first() or Organization.objects.create(name=f"Org {gen_id}", level=0, sort=1, is_use=True)
    shift = Shift.objects.first() or Shift.objects.create(shift_vi="Ca 1", shift_en="Shift 1", shift_kr="교대 1")

    user = User.objects.create(gen_id=gen_id, full_name=full_name, org=org, shift=shift, password="")
    user.set_password("Str0ngPass@1")
    user.status = User.StatusChoices.APPROVED
    user.save(update_fields=["password", "status"])
    return user


class RefreshTokenGenerationTests(TestCase):
    """Sinh token + băm — thuần hàm, không cần phiên."""

    databases = "__all__"

    def test_token_has_prefix_and_high_entropy(self):
        token = rt.generate_raw_token()
        self.assertTrue(token.startswith(rt.TOKEN_PREFIX))
        # `token_urlsafe(48)` sinh ~64 ký tự ⇒ token dài > 60.
        self.assertGreater(len(token), 60)

    def test_tokens_are_unique(self):
        tokens = {rt.generate_raw_token() for _ in range(200)}
        self.assertEqual(len(tokens), 200)

    def test_hash_is_deterministic_and_hex64(self):
        token = rt.generate_raw_token()
        first = rt.hash_token(token)
        self.assertEqual(first, rt.hash_token(token))
        self.assertEqual(len(first), 64)
        int(first, 16)  # phải là hex hợp lệ

    def test_hash_never_equals_plaintext(self):
        # INVARIANT 4: DB không chứa plaintext.
        token = rt.generate_raw_token()
        self.assertNotEqual(rt.hash_token(token), token)
        self.assertNotIn(token, rt.hash_token(token))

    def test_different_tokens_have_different_hashes(self):
        self.assertNotEqual(rt.hash_token(rt.generate_raw_token()), rt.hash_token(rt.generate_raw_token()))


class RefreshTokenFamilyTests(TestCase):
    """Tạo phiên, xoay token, phát hiện tái sử dụng."""

    # Bảng `user`/`info` nằm ở PostgreSQL schema riêng (xem settings DB_SCHEMAS)
    # ⇒ test phải có quyền truy cập MỌI alias DB, không chỉ `default`.
    databases = "__all__"

    def setUp(self):
        self.user = make_user("12345678", full_name="Family User")
        self.raw, self.session = rt.create_session(self.user)

    # ---- INVARIANT 1: token dùng 1 lần ----
    def test_rotate_returns_new_tokens(self):
        result = rt.rotate(self.raw)
        self.assertTrue(result["refresh_token"].startswith(rt.TOKEN_PREFIX))
        self.assertTrue(result["access_token"])
        self.assertNotEqual(result["refresh_token"], self.raw)

    def test_old_token_revoked_after_rotate(self):
        rt.rotate(self.raw)
        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.revoked_at)
        self.assertTrue(self.session.was_rotated)

    def test_new_token_active_after_rotate(self):
        result = rt.rotate(self.raw)
        new_session = RefreshTokenSession.objects.get(token_hash=rt.hash_token(result["refresh_token"]))
        self.assertIsNone(new_session.revoked_at)
        self.assertTrue(new_session.is_active)

    def test_rotation_keeps_same_family(self):
        result = rt.rotate(self.raw)
        new_session = RefreshTokenSession.objects.get(token_hash=rt.hash_token(result["refresh_token"]))
        self.assertEqual(new_session.family_id, self.session.family_id)
        self.assertEqual(new_session.parent_id, self.session.id)

    # ---- INVARIANT 3: reuse ⇒ thu hồi cả family ----
    def test_reusing_rotated_token_raises_reuse(self):
        rt.rotate(self.raw)
        with self.assertRaises(rt.RefreshReuseDetected):
            rt.rotate(self.raw)

    def test_reuse_revokes_whole_family(self):
        first = rt.rotate(self.raw)
        live_session = RefreshTokenSession.objects.get(token_hash=rt.hash_token(first["refresh_token"]))
        self.assertIsNone(live_session.revoked_at)

        # Kẻ tấn công dùng lại token cũ ⇒ cả family chết.
        with self.assertRaises(rt.RefreshReuseDetected):
            rt.rotate(self.raw)

        live_session.refresh_from_db()
        self.assertIsNotNone(live_session.revoked_at)

    def test_reuse_also_kills_newest_token(self):
        first = rt.rotate(self.raw)
        second = rt.rotate(first["refresh_token"])
        newest = RefreshTokenSession.objects.get(token_hash=rt.hash_token(second["refresh_token"]))

        with self.assertRaises(rt.RefreshReuseDetected):
            rt.rotate(self.raw)

        newest.refresh_from_db()
        self.assertIsNotNone(newest.revoked_at)

    def test_reuse_error_carries_machine_readable_code(self):
        rt.rotate(self.raw)
        with self.assertRaises(rt.RefreshReuseDetected) as ctx:
            rt.rotate(self.raw)
        self.assertEqual(ctx.exception.code, "AUTH_REFRESH_REUSE_DETECTED")
        self.assertEqual(ctx.exception.status_code, 401)

    # ---- Kịch bản thực tế: người dùng bấm F5 ----
    def test_reload_scenario_client_retry_kills_session(self):
        """Tái hiện đúng lỗi FE vừa gặp — mô tả hành vi PHÍA SERVER.

        Người dùng F5: client bay refresh, server XOAY token và trả 200. Client
        không giải mã được response (handshake chưa xong) nên gửi LẠI token cũ.

        Kết quả ở server là reuse ⇒ cả family bị thu hồi, kể cả token MỚI vừa
        cấp cho client. Đây là hành vi ĐÚNG của server (bảo vệ INVARIANT 1/3) —
        test này chốt lại để lần sau ai đó "nới lỏng" reuse detection cũng phải
        thấy test này đỏ, chứ không âm thầm phá bảo mật.
        """
        first = rt.rotate(self.raw)  # F5 lần 1: xoay thành công
        newest_hash = rt.hash_token(first["refresh_token"])

        # Client gửi lại token cũ (fallback plaintext trước khi sửa FE).
        with self.assertRaises(rt.RefreshReuseDetected):
            rt.rotate(self.raw)

        # Token MỚI cũng chết theo ⇒ phiên bị đăng xuất, buộc đăng nhập lại.
        self.assertIsNotNone(RefreshTokenSession.objects.get(token_hash=newest_hash).revoked_at)

    def test_single_refresh_does_not_kill_new_session(self):
        """Ngược lại: chỉ xoay 1 lần thì phiên phải sống bình thường."""
        first = rt.rotate(self.raw)
        second = rt.rotate(first["refresh_token"])
        self.assertTrue(second["refresh_token"].startswith(rt.TOKEN_PREFIX))
        self.assertIsNone(RefreshTokenSession.objects.get(token_hash=rt.hash_token(second["refresh_token"])).revoked_at)

    # ---- Token lạ / hỏng ----
    def test_unknown_token_raises_invalid(self):
        with self.assertRaises(rt.RefreshTokenInvalid):
            rt.rotate("rt_" + "x" * 64)

    def test_non_prefixed_token_raises_invalid(self):
        # Token JWT cũ hoặc rác — không có tiền tố `rt_` ⇒ không phải do hệ
        # thống này cấp.
        with self.assertRaises(rt.RefreshTokenInvalid):
            rt.rotate("some.jwt.token")

    def test_empty_token_raises_missing(self):
        with self.assertRaises(rt.RefreshTokenMissing):
            rt.rotate("")

    # ---- Hết hạn ----
    def test_idle_expired_token_raises_expired(self):
        self.session.expires_at = timezone.now() - timedelta(seconds=1)
        self.session.save(update_fields=["expires_at"])
        with self.assertRaises(rt.RefreshTokenExpired):
            rt.rotate(self.raw)

    def test_absolute_expired_token_raises_expired(self):
        self.session.absolute_expires_at = timezone.now() - timedelta(seconds=1)
        self.session.save(update_fields=["absolute_expires_at"])
        with self.assertRaises(rt.RefreshTokenExpired):
            rt.rotate(self.raw)

    def test_rotation_does_not_extend_absolute_lifetime(self):
        # spec §38: xoay token KHÔNG reset mốc hết hạn tuyệt đối.
        original_absolute = self.session.absolute_expires_at
        result = rt.rotate(self.raw)
        new_session = RefreshTokenSession.objects.get(token_hash=rt.hash_token(result["refresh_token"]))
        self.assertEqual(new_session.absolute_expires_at, original_absolute)

    # ---- INVARIANT 7/8: nhiều phiên độc lập ----
    def test_second_login_creates_independent_family(self):
        other_raw, other_session = rt.create_session(self.user)
        self.assertNotEqual(other_session.family_id, self.session.family_id)
        self.assertEqual(RefreshTokenSession.active_for_user(self.user).count(), 2)

    def test_revoking_one_session_leaves_others_active(self):
        other_raw, other_session = rt.create_session(self.user)
        rt.revoke_session(self.session)
        other_session.refresh_from_db()
        self.assertIsNone(other_session.revoked_at)
        # Token của phiên còn lại vẫn xoay được.
        self.assertTrue(rt.rotate(other_raw)["refresh_token"])

    def test_revoked_by_logout_is_not_reuse(self):
        # spec §16: bị thu hồi có chủ đích (không có replaced_by) ≠ reuse.
        rt.revoke_session(self.session)
        with self.assertRaises(rt.RefreshTokenRevoked):
            rt.rotate(self.raw)

    def test_revoke_family_leaves_other_family_active(self):
        other_raw, other_session = rt.create_session(self.user)
        rt.revoke_family(self.session.family_id)
        other_session.refresh_from_db()
        self.assertIsNone(other_session.revoked_at)

    def test_revoke_all_for_user_revokes_everything(self):
        rt.create_session(self.user)
        rt.create_session(self.user)
        rt.revoke_all_for_user(self.user)
        self.assertEqual(RefreshTokenSession.active_for_user(self.user).count(), 0)

    def test_inactive_user_family_revoked(self):
        # `is_active` là PROPERTY suy ra từ `status` ⇒ phải đổi `status`,
        # gán `is_active` sẽ không tồn tại trên instance.
        self.user.status = User.StatusChoices.WAITING
        self.user.save(update_fields=["status"])
        with self.assertRaises(rt.RefreshTokenRevoked):
            rt.rotate(self.raw)
        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.revoked_at)


class RefreshTokenRaceTests(TestCase):
    """INVARIANT 11: 2 request refresh SONG SONG cùng 1 token."""

    databases = "__all__"

    def setUp(self):
        self.user = make_user("98765432", full_name="Race User")
        self.raw, self.session = rt.create_session(self.user)

    def test_parallel_refresh_yields_single_valid_descendant(self):
        """Hai lần xoay cùng token: 1 thắng, 1 bị từ chối.

        `select_for_update()` khoá dòng nên request thứ hai phải chờ; khi vào
        được transaction nó thấy token đã `revoked_at` + `replaced_by` ⇒ REUSE.
        Đường nào thắng không quan trọng — điều quan trọng là DB cuối cùng
        KHÔNG được có 2 token active sinh ra từ 1 token gốc.
        """
        outcomes = []
        barrier = threading.Barrier(2)

        def worker():
            barrier.wait()
            try:
                rt.rotate(self.raw)
                outcomes.append("ok")
            except rt.RefreshReuseDetected:
                outcomes.append("reuse")
            except rt.RefreshTokenError:
                outcomes.append("denied")

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(outcomes), 2)
        # Không được cả 2 cùng thành công — đó là lỗi rotation.
        self.assertLessEqual(outcomes.count("ok"), 1)
        # Mỗi token gốc chỉ có tối đa 1 token con.
        self.assertLessEqual(RefreshTokenSession.objects.filter(parent_id=self.session.id).count(), 1)
        # Không có 2 token active trong cùng family.
        active = RefreshTokenSession.objects.filter(family_id=self.session.family_id, revoked_at__isnull=True).count()
        self.assertLessEqual(active, 1)


class RefreshTokenPurgeTests(TestCase):
    """Job dọn bản ghi hết hạn (spec §55)."""

    databases = "__all__"

    def setUp(self):
        self.user = make_user("11223344", full_name="Purge User")

    def test_purge_keeps_recent_but_deletes_old(self):
        fresh = rt.create_session(self.user)[1]
        old = rt.create_session(self.user)[1]
        RefreshTokenSession.objects.filter(id=old.id).update(absolute_expires_at=timezone.now() - timedelta(days=90))

        deleted = RefreshTokenSession.purge_expired(keep_days=30)

        self.assertEqual(deleted, 1)
        self.assertTrue(RefreshTokenSession.objects.filter(id=fresh.id).exists())
        self.assertFalse(RefreshTokenSession.objects.filter(id=old.id).exists())

    @override_settings(REFRESH_SESSION_KEEP_DAYS=30)
    def test_task_delegates_to_model(self):
        from apps.accounts.tasks import purge_expired_refresh_sessions

        session = rt.create_session(self.user)[1]
        RefreshTokenSession.objects.filter(id=session.id).update(absolute_expires_at=timezone.now() - timedelta(days=60))
        self.assertEqual(purge_expired_refresh_sessions(), 1)


class AccessTokenSessionClaimTests(TestCase):
    """Access token mang `sid` để truy vết phiên (spec §46)."""

    databases = "__all__"

    def test_access_token_contains_sid(self):
        from libs.auth.jwt_utils import decode_access_token, generate_access_token

        user = make_user("55667788", full_name="Sid User")
        sid = str(uuid.uuid4())
        payload = decode_access_token(generate_access_token(user, sid=sid))
        self.assertEqual(payload.get("sid"), sid)

def _flatten(value):
    """Duyệt đệ quy mọi giá trị trong dict/list để test tìm mã lỗi."""
    if isinstance(value, dict):
        for item in value.values():
            yield from _flatten(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _flatten(item)
    else:
        yield value


class ViewLevelTokenFamilyTests(TestCase):
    """Luồng HTTP thật: login → refresh → reuse → logout.

    Kiểm chứng contract FE thực sự dùng: refresh nhận token qua
    `Authorization: Bearer` (không cần body), dùng lại token cũ ⇒ 401 kèm mã
    `AUTH_REFRESH_REUSE_DETECTED`, logout không đụng thiết bị khác, và danh
    sách phiên không lộ token/hash.
    """

    databases = "__all__"

    def setUp(self):
        from django.core.cache import cache
        from rest_framework.test import APIRequestFactory, force_authenticate

        # Mỗi test login nhiều lần; throttle `login` chỉ cho 5 request/phút
        # (đúng để chống brute-force) nên phải xoá cache throttle giữa các test,
        # nếu không test sẽ nhận 429 và fail vì lý do không liên quan.
        cache.clear()
        self.factory = APIRequestFactory()
        self.user = make_user("76543210", full_name="View User")
        self.force_authenticate = force_authenticate

    def _login(self):
        from apps.accounts.views import LoginView

        request = self.factory.post("/accounts/auth/login", {"account": "76543210", "password": "Str0ngPass@1"}, content_type="application/json")
        return LoginView.as_view()(request)

    def _refresh(self, raw_token):
        from apps.accounts.views import RefreshTokenView

        request = self.factory.post("/accounts/auth/refresh", {}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {raw_token}")
        return RefreshTokenView.as_view()(request)

    def test_login_returns_opaque_refresh_and_creates_session(self):
        from apps.accounts.models import RefreshTokenSession

        response = self._login()
        self.assertEqual(response.status_code, 200)
        refresh = response.data["data"]["refresh"]
        # Token phải OPAQUE có tiền tố `rt_`, KHÔNG phải JWT (JWT có 2 dấu chấm).
        self.assertTrue(refresh.startswith("rt_"))
        self.assertEqual(refresh.count("."), 0)
        self.assertEqual(RefreshTokenSession.active_for_user(self.user).count(), 1)

    def test_refresh_accepts_bearer_header_without_body(self):
        refresh = self._login().data["data"]["refresh"]
        response = self._refresh(refresh)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.data["data"]["refresh"], refresh)

    def test_refresh_still_accepts_legacy_body(self):
        from apps.accounts.views import RefreshTokenView

        refresh = self._login().data["data"]["refresh"]
        request = self.factory.post("/accounts/auth/refresh", {"refresh": refresh}, content_type="application/json")
        self.assertEqual(RefreshTokenView.as_view()(request).status_code, 200)

    def test_logout_revokes_only_current_session(self):
        from apps.accounts.models import RefreshTokenSession
        from apps.accounts.views import LogoutView

        first = self._login().data["data"]["refresh"]
        # Đăng nhập lần 2 (thiết bị khác) ⇒ family thứ 2.
        second_refresh = self._login().data["data"]["refresh"]
        self.assertEqual(RefreshTokenSession.active_for_user(self.user).count(), 2)

        request = self.factory.post("/accounts/auth/logout", {}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {first}")
        self.assertEqual(LogoutView.as_view()(request).status_code, 200)

        # Phiên thứ 2 vẫn xoay được ⇒ logout không đụng thiết bị khác (INVARIANT 8).
        self.assertEqual(self._refresh(second_refresh).status_code, 200)

    def test_logout_is_idempotent_with_dead_token(self):
        from apps.accounts.views import LogoutView

        refresh = self._login().data["data"]["refresh"]
        self._refresh(refresh)
        # Token đã bị xoay ⇒ logout vẫn phải 200 (client không bị kẹt).
        request = self.factory.post("/accounts/auth/logout", {}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {refresh}")
        self.assertEqual(LogoutView.as_view()(request).status_code, 200)

    def test_logout_all_revokes_every_session(self):
        from apps.accounts.models import RefreshTokenSession
        from apps.accounts.views import LogoutAllView

        refresh = self._login().data["data"]["refresh"]
        request = self.factory.post("/accounts/auth/logout-all", {}, content_type="application/json")
        self.force_authenticate(request, user=self.user)
        response = LogoutAllView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RefreshTokenSession.active_for_user(self.user).count(), 0)
        # Token cũ không dùng được nữa.
        self.assertEqual(self._refresh(refresh).status_code, 401)

    def test_session_list_never_exposes_secrets(self):
        from apps.accounts.views import SessionListView

        self._login()
        request = self.factory.get("/accounts/auth/sessions")
        self.force_authenticate(request, user=self.user)
        response = SessionListView.as_view()(request)
        self.assertEqual(response.status_code, 200)

        rows = response.data["data"]
        self.assertEqual(len(rows), 1)
        for row in rows:
            # INVARIANT 4 / spec §19: không rò token hay hash.
            self.assertNotIn("token_hash", row)
            self.assertNotIn("refresh", row)
            self.assertNotIn("family_id", row)
            self.assertIn("device", row)

    def test_session_revoke_only_own_session(self):
        from apps.accounts.models import RefreshTokenSession
        from apps.accounts.views import SessionRevokeView

        self._login()
        mine = RefreshTokenSession.active_for_user(self.user).first()

        # Người khác không thể thu hồi phiên này ⇒ 404 (không lộ tồn tại).
        other = make_user("24681357", full_name="Other User")
        request = self.factory.post("/accounts/auth/sessions/revoke", {"session_id": str(mine.id)}, content_type="application/json")
        self.force_authenticate(request, user=other)
        self.assertEqual(SessionRevokeView.as_view()(request).status_code, 404)
        mine.refresh_from_db()
        self.assertIsNone(mine.revoked_at)

        # Chủ phiên thì thu hồi được.
        request = self.factory.post("/accounts/auth/sessions/revoke", {"session_id": str(mine.id)}, content_type="application/json")
        self.force_authenticate(request, user=self.user)
        self.assertEqual(SessionRevokeView.as_view()(request).status_code, 200)
        refresh = self._login().data["data"]["refresh"]
        self.assertEqual(self._refresh(refresh).status_code, 200)

        # Gửi lại token cũ ⇒ phát hiện tái sử dụng.
        response = self._refresh(refresh)
        self.assertEqual(response.status_code, 401)
        # Mã lỗi máy đọc được phải có mặt để FE không phải đoán qua câu chữ.
        errors = response.data["errors"]
        self.assertTrue(any("AUTH_REFRESH_REUSE_DETECTED" in str(value) for value in _flatten(errors)))
    def test_sid_optional_for_backward_compat(self):
        from types import SimpleNamespace

        from libs.auth.jwt_utils import generate_access_token

        user = SimpleNamespace(id=1, gen_id="11112222")
        # Không truyền `sid` vẫn phải sinh được token (nơi gọi cũ chưa đổi).
        self.assertTrue(generate_access_token(user))

class MultiSchemaTransactionTests(TestCase):
	"""Transaction phải mở trên ĐÚNG DB alias của model.

	BUG THẬT ĐÃ XẢY RA: `transaction.atomic()` không tham số mở transaction trên
	`default`, còn `RefreshTokenSession` nằm ở connection `schema_user`. Với
	multi-schema, `select_for_update()` ném
	    TransactionManagementError: select_for_update cannot be used outside of
	    a transaction
	⇒ endpoint `/accounts/auth/refresh` trả 500 và cơ chế khoá dòng chống race
	khi xoay token KHÔNG hoạt động trên môi trường thật.

	Test suite không bắt được vì `config/settings/test.py` gom mọi schema về
	`public` (mọi alias trùng nhau) ⇒ các test này kiểm tra đúng alias được
	dùng thay vì kiểm tra hành vi quan sát được.
	"""

	databases = "__all__"

	def test_session_alias_matches_model_write_db(self):
		from django.db import router

		from apps.accounts.models import RefreshTokenSession
		from libs.auth import refresh_tokens as rt

		self.assertEqual(rt.session_db_alias(), router.db_for_write(RefreshTokenSession))

	def test_rotate_opens_transaction_on_that_alias(self):
		"""`rotate()` phải bọc `transaction.atomic(using=<alias của model>)`."""
		import inspect

		from libs.auth import refresh_tokens as rt

		source = inspect.getsource(rt.rotate)
		self.assertIn("transaction.atomic(using=session_db_alias())", source)
		# Chốt hồi quy: KHÔNG được còn `atomic()` trần (mở nhầm connection).
		self.assertNotIn("with transaction.atomic():", source)

	def test_login_opens_transaction_on_that_alias(self):
		import inspect

		from apps.accounts.services import auth_service

		source = inspect.getsource(auth_service.AuthService.login)
		self.assertIn("transaction.atomic(using=rt.session_db_alias())", source)

	def test_dispatch_reorder_opens_transaction_on_model_alias(self):
		import inspect

		from apps.info import dispatch

		source = inspect.getsource(dispatch)
		self.assertIn("transaction.atomic(using=router.db_for_write(model)", source)

	def test_select_for_update_runs_inside_a_transaction(self):
		"""Hành vi quan sát được: khoá dòng phải chạy được, không ném lỗi."""
		from django.db import connections

		from libs.auth import refresh_tokens as rt

		seen = {}

		def spy(raw_token, lock=False):
			if lock:
				seen["in_atomic"] = connections[rt.session_db_alias()].in_atomic_block
			raise rt.RefreshTokenInvalid()

		from unittest.mock import patch

		with patch.object(rt, "_resolve_session", side_effect=spy):
			with self.assertRaises(rt.RefreshTokenInvalid):
				rt.rotate("rt_bat_ky_abcdefgh")
		self.assertTrue(seen.get("in_atomic"), "select_for_update phải nằm trong transaction")


class LegacyJwtCompatibilityTests(TestCase):
    """Token JWT CŨ (trước khi lên Token Family) vẫn refresh được 1 lần.

    Không có nhánh này thì lúc deploy, MỌI phiên đang đăng nhập đều bị đăng xuất
    oàn dù refresh token còn hạn 7 ngày.
    """

    databases = "__all__"

    def setUp(self):
        from django.core.cache import cache
        from rest_framework.test import APIRequestFactory

        cache.clear()
        self.factory = APIRequestFactory()
        self.user = make_user("31415926", full_name="Legacy User")

    def _legacy_token(self):
        from libs.auth.jwt_utils import generate_refresh_token

        return generate_refresh_token(self.user)

    def test_legacy_jwt_rotates_into_opaque(self):
        from libs.auth import refresh_tokens as rt

        result = rt.rotate_legacy_jwt(self._legacy_token())
        self.assertTrue(result["refresh_token"].startswith(rt.TOKEN_PREFIX))
        self.assertTrue(result["access_token"])
        self.assertEqual(result["session"].user_id, self.user.id)

    def test_legacy_jwt_blacklisted_after_use(self):
        from libs.auth import refresh_tokens as rt

        legacy = self._legacy_token()
        rt.rotate_legacy_jwt(legacy)
        # Dùng lại token cũ ⇒ phải bị từ chối (INVARIANT 1).
        with self.assertRaises(rt.RefreshTokenRevoked):
            rt.rotate_legacy_jwt(legacy)

    def test_legacy_jwt_invalid_token_rejected(self):
        from libs.auth import refresh_tokens as rt

        with self.assertRaises(rt.RefreshTokenInvalid):
            rt.rotate_legacy_jwt("khong-phai-jwt-hop-le")

    def test_refresh_endpoint_accepts_legacy_token(self):
        from apps.accounts.views import RefreshTokenView

        request = self.factory.post("/accounts/auth/refresh", {}, content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {self._legacy_token()}")
        response = RefreshTokenView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        # Response phải trả token OPAQUE để client lưu lại dùng tiếp.
        self.assertTrue(response.data["data"]["refresh"].startswith("rt_"))

    def test_logout_with_legacy_jwt_revokes_it_on_server(self):
        """Logout bằng token JWT cũ phải thu hồi được, không chỉ xoá ở client."""
        from apps.accounts.services.auth_service import AuthService
        from libs.auth import refresh_tokens as rt
        from libs.auth.jwt_utils import generate_refresh_token, is_token_blacklisted
        import jwt as pyjwt

        legacy = generate_refresh_token(self.user)
        jti = pyjwt.decode(legacy, options={"verify_signature": False})["jti"]

        self.assertTrue(AuthService.logout(legacy))
        self.assertTrue(is_token_blacklisted(jti), "token JWT cũ phải bị thu hồi sau logout")
        # Và không dùng lại được nữa.
        with self.assertRaises(rt.RefreshTokenRevoked):
            rt.rotate_legacy_jwt(legacy)

    def test_access_token_cannot_be_used_as_refresh(self):
        """Token access KHÔNG được dùng để refresh (lỗi phổ biến)."""
        from libs.auth import refresh_tokens as rt
        from libs.auth.jwt_utils import generate_access_token

        access = generate_access_token(self.user)
        with self.assertRaises(rt.RefreshTokenInvalid):
            rt.rotate_legacy_jwt(access)