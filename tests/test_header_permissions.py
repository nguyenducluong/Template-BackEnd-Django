"""
Unit tests cho quyền T1 (apps/info/permissions.py) + fix has_power + wiring view.

Không cần DB: toàn bộ ORM được patch bằng unittest.mock, cache được patch
thành MagicMock (không phụ thuộc Redis/LocMem). SimpleTestCase cũng chặn
truy cập DB thật — nếu test nào lỡ gọi query sẽ fail ngay.

Chạy:  python -m pytest tests/test_header_permissions.py -q
"""
import importlib
from types import SimpleNamespace
from unittest import mock
from unittest.mock import patch

from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.test import SimpleTestCase, override_settings

from apps.ai.tools.base import ToolSpec, has_power
from apps.info.models import HeaderRegistration, SystemPermission, UserHeaderRegistration, UserSystemPermissionRegistration
from apps.info.permissions import (
    PERM_CACHE_KEY,
    HasHeaderPermission,
    get_perm_cache_key,
    get_user_permitted_header_ids,
    invalidate_org_permission_cache,
    invalidate_permission_cache,
    user_has_header_permission,
)

USER = SimpleNamespace(id=7, org_id=22, is_authenticated=True)
USER_KEY = get_perm_cache_key(7)


class CacheKeyTests(SimpleTestCase):
    """Định dạng key cache quyền."""

    def test_key_format(self):
        self.assertEqual(USER_KEY, PERM_CACHE_KEY.format(user_id=7))
        self.assertEqual(USER_KEY, "systems:perm:7")

    def test_invalid_user_returns_empty_without_cache(self):
        with patch("apps.info.permissions.cache") as cache_mock:
            self.assertEqual(get_user_permitted_header_ids(None), [])
            self.assertEqual(get_user_permitted_header_ids(SimpleNamespace()), [])
            cache_mock.get.assert_not_called()


class FetchPermittedHeaderIdsTests(SimpleTestCase):
    """_fetch_permitted_header_ids + cache hit/miss (get_user_permitted_header_ids)."""

    def setUp(self):
        # patch manager ORM + cache → không đụng DB/Redis thật
        p_hdr = patch("apps.info.permissions.HeaderRegistration.objects")
        p_uhdr = patch("apps.info.permissions.UserHeaderRegistration.objects")
        p_cache = patch("apps.info.permissions.cache")
        self.hdr_mgr = p_hdr.start()
        self.uhdr_mgr = p_uhdr.start()
        self.cache_mock = p_cache.start()
        for p in (p_hdr, p_uhdr, p_cache):
            self.addCleanup(p.stop)
        # mặc định: không có grant nào + cache miss
        self.hdr_mgr.filter.return_value.values_list.return_value = []
        self.uhdr_mgr.filter.return_value.values_list.return_value = []
        self.cache_mock.get.return_value = None

    def test_merges_public_and_private_ids_sorted_unique(self):
        self.hdr_mgr.filter.return_value.values_list.return_value = [3, 1]
        self.uhdr_mgr.filter.return_value.values_list.return_value = [3, 2]

        result = get_user_permitted_header_ids(USER)

        self.assertEqual(result, [1, 2, 3])  # unique + tăng dần
        # đúng pattern get_registered_structure: công khai = NO_REGISTRATION + APPROVED
        self.hdr_mgr.filter.assert_called_once_with(
            org_id=USER.org_id,
            type=HeaderRegistration.TypeChoices.NO_REGISTRATION,
            status=HeaderRegistration.StatusChoices.APPROVED,
        )
        self.uhdr_mgr.filter.assert_called_once_with(
            registered_by_id=USER.id,
            status=UserHeaderRegistration.StatusChoices.APPROVED,
        )
        # cache miss → set(key, ids, TTL lấy từ settings)
        expected_ttl = getattr(settings, "SYSTEMS_PERM_CACHE_TTL", 60)
        self.cache_mock.set.assert_called_once_with(USER_KEY, [1, 2, 3], expected_ttl)

    def test_user_without_org_skips_public_query(self):
        get_user_permitted_header_ids(SimpleNamespace(id=7))
        self.hdr_mgr.filter.assert_not_called()
        self.uhdr_mgr.filter.assert_called_once()

    def test_cache_hit_skips_db_fetch(self):
        self.cache_mock.get.return_value = [9]
        with patch("apps.info.permissions._fetch_permitted_header_ids") as fetch_mock:
            result = get_user_permitted_header_ids(USER)
        self.assertEqual(result, [9])
        fetch_mock.assert_not_called()
        self.cache_mock.set.assert_not_called()

    @override_settings(SYSTEMS_PERM_CACHE_TTL=5)
    def test_ttl_read_from_settings(self):
        get_user_permitted_header_ids(USER)
        self.cache_mock.set.assert_called_once_with(USER_KEY, [], 5)

    def test_result_cached_even_when_empty(self):
        # quyền rỗng vẫn phải cache (tránh đấm query mỗi request)
        get_user_permitted_header_ids(USER)
        self.cache_mock.set.assert_called_once()


class UserHasHeaderPermissionTests(SimpleTestCase):
    """user_has_header_permission — so khớp id + fail-closed với id sai kiểu."""

    def test_valid_header_ids(self):
        with patch("apps.info.permissions.get_user_permitted_header_ids", return_value=[1, 2]) as fetch:
            self.assertTrue(user_has_header_permission(USER, 1))
            self.assertTrue(user_has_header_permission(USER, "2"))  # FE gửi string
            self.assertFalse(user_has_header_permission(USER, 99))
            self.assertEqual(fetch.call_count, 3)

    def test_invalid_header_id_fails_closed_without_db(self):
        with patch("apps.info.permissions.get_user_permitted_header_ids") as fetch:
            self.assertFalse(user_has_header_permission(USER, "abc"))
            self.assertFalse(user_has_header_permission(USER, None))
            fetch.assert_not_called()  # id sai kiểu → không cần tra cache/DB
            # user=None → getter tự trả [] (vẫn False, fail-closed)
            self.assertFalse(user_has_header_permission(None, 1))

    def test_demo_header_bypass_without_db(self):
        """Header demo 10000: user hợp lệ qua luôn, không tra cache/DB."""
        from apps.info.permissions import DEMO_HEADER_IDS

        self.assertIn(10000, DEMO_HEADER_IDS)
        with patch("apps.info.permissions.get_user_permitted_header_ids") as fetch:
            self.assertTrue(user_has_header_permission(USER, 10000))
            self.assertTrue(user_has_header_permission(USER, "10000"))  # FE gửi string
            fetch.assert_not_called()
            # user không hợp lệ vẫn fail-closed (chưa đăng nhập / thiếu id)
            self.assertFalse(user_has_header_permission(None, 10000))
            self.assertFalse(user_has_header_permission(SimpleNamespace(), 10000))


class InvalidateCacheTests(SimpleTestCase):
    """invalidate_permission_cache / invalidate_org_permission_cache."""

    def test_invalidate_single_user(self):
        with patch("apps.info.permissions.cache") as cache_mock:
            invalidate_permission_cache(7)
            cache_mock.delete.assert_called_once_with(USER_KEY)

    def test_invalidate_org_deletes_all_users(self):
        with patch("apps.accounts.models.User.objects") as user_mgr, patch("apps.info.permissions.cache") as cache_mock:
            user_mgr.filter.return_value.values_list.return_value = [7, 8]
            invalidate_org_permission_cache(22)
            user_mgr.filter.assert_called_once_with(org_id=22)
            cache_mock.delete_many.assert_called_once_with(["systems:perm:7", "systems:perm:8"])

    def test_invalidate_org_without_org_is_noop(self):
        with patch("apps.accounts.models.User.objects") as user_mgr, patch("apps.info.permissions.cache") as cache_mock:
            invalidate_org_permission_cache(None)
            user_mgr.filter.assert_not_called()
            cache_mock.delete_many.assert_not_called()


class HasHeaderPermissionTests(SimpleTestCase):
    """DRF permission class: 403 đúng lúc, cho qua khi view tự validate 400."""

    def _request(self, data=None, auth=True):
        return SimpleNamespace(
            user=SimpleNamespace(is_authenticated=auth),
            data=data if data is not None else {},
        )

    def test_unauthenticated_denied(self):
        with patch("apps.info.permissions.user_has_header_permission") as checker:
            has_perm = HasHeaderPermission().has_permission(self._request(auth=False), SimpleNamespace())
            self.assertFalse(has_perm)
            checker.assert_not_called()

    def test_view_header_id_checked(self):
        # HeaderNDetailsView khai header_id cố định → dùng trực tiếp
        with patch("apps.info.permissions.user_has_header_permission", return_value=True) as checker:
            view = SimpleNamespace(header_id=2)
            self.assertTrue(HasHeaderPermission().has_permission(self._request(), view))
            checker.assert_called_once_with(mock.ANY, 2)

        with patch("apps.info.permissions.user_has_header_permission", return_value=False):
            self.assertFalse(HasHeaderPermission().has_permission(self._request(), view))

    def test_body_header_id_checked(self):
        # dispatcher init_data lấy header_id từ body
        with patch("apps.info.permissions.user_has_header_permission", return_value=True) as checker:
            req = self._request(data={"header_id": "3", "func": "details"})
            self.assertTrue(HasHeaderPermission().has_permission(req, SimpleNamespace()))
            checker.assert_called_once_with(mock.ANY, "3")

    def test_missing_header_id_defers_to_view_400(self):
        with patch("apps.info.permissions.user_has_header_permission") as checker:
            self.assertTrue(HasHeaderPermission().has_permission(self._request(data={}), SimpleNamespace()))
            checker.assert_not_called()

    def test_non_int_header_id_defers_to_view_400(self):
        with patch("apps.info.permissions.user_has_header_permission") as checker:
            req = self._request(data={"header_id": "abc"})
            self.assertTrue(HasHeaderPermission().has_permission(req, SimpleNamespace()))
            checker.assert_not_called()

    def test_non_dict_body_defers_to_view(self):
        # body JSON array → không có .get → không nổ, view tự validate
        with patch("apps.info.permissions.user_has_header_permission") as checker:
            self.assertTrue(HasHeaderPermission().has_permission(self._request(data=[1, 2]), SimpleNamespace()))
            checker.assert_not_called()


class HasPowerTests(SimpleTestCase):
    """has_power — fix `power__code` FieldError + lọc type + fail-closed (P1.5)."""

    def setUp(self):
        p_sp = patch("apps.info.models.SystemPermission.objects")
        p_usp = patch("apps.info.models.UserSystemPermissionRegistration.objects")
        self.sp_mgr = p_sp.start()
        self.usp_mgr = p_usp.start()
        self.addCleanup(p_sp.stop)
        self.addCleanup(p_usp.stop)
        # mặc định: không có grant nào
        self.sp_mgr.filter.return_value.values_list.return_value = []
        self.usp_mgr.filter.return_value.values_list.return_value = []

    def test_org_grant_filters_no_registration_and_approved(self):
        self.sp_mgr.filter.return_value.values_list.return_value = [(1, "Save memo SQCI")]

        self.assertTrue(has_power(USER, [1]))

        # type=NO_REGISTRATION: quyền NEED_REGISTRATION không tự áp cho cả org
        self.sp_mgr.filter.assert_called_once_with(
            org_id=USER.org_id,
            type=SystemPermission.TypeChoices.NO_REGISTRATION,
            status=SystemPermission.StatusChoices.APPROVED,
        )
        # quyền user: registration + permission cha đều phải APPROVED
        self.usp_mgr.filter.assert_called_once_with(
            registered_by_id=USER.id,
            status=UserSystemPermissionRegistration.StatusChoices.APPROVED,
            system_permission__status=SystemPermission.StatusChoices.APPROVED,
        )

    def test_match_by_power_id_int_and_string(self):
        self.sp_mgr.filter.return_value.values_list.return_value = [(1, "Save memo SQCI")]
        self.assertTrue(has_power(USER, [1]))  # SystemPower.id (chuẩn P1.6)
        self.assertTrue(has_power(USER, ["1"]))  # chuỗi số

    def test_match_by_power_en_name(self):
        self.sp_mgr.filter.return_value.values_list.return_value = [(1, "Save memo SQCI")]
        self.assertTrue(has_power(USER, ["Save memo SQCI"]))  # exact match (P1.5)
        self.assertFalse(has_power(USER, ["save memo sqci"]))  # không fuzzy

    def test_user_registration_grant_without_org_grant(self):
        self.usp_mgr.filter.return_value.values_list.return_value = [(5, "Other Power")]
        self.assertTrue(has_power(USER, [5]))
        self.assertFalse(has_power(USER, [99]))

    def test_no_match_returns_false(self):
        self.assertFalse(has_power(USER, [1]))
        self.assertFalse(has_power(USER, ["view_profile"]))

    def test_query_error_fails_closed_without_raising(self):
        self.sp_mgr.filter.side_effect = RuntimeError("db down")
        self.assertFalse(has_power(USER, [1]))  # không nổ FieldError/Exception

    def test_empty_powers_or_anonymous_skips_query(self):
        self.assertFalse(has_power(USER, []))
        self.sp_mgr.filter.assert_not_called()
        self.assertFalse(has_power(None, [1]))
        self.assertFalse(has_power(SimpleNamespace(), [1]))


class ToolSpecCallTests(SimpleTestCase):
    """ToolSpec.call: check quyền nằm trong try — không để 500 (S3)."""

    def _spec(self, handler=None, powers=("x",)):
        return ToolSpec("t1", "desc", {"type": "object"}, handler or (lambda u, a: {"ok": True}), required_powers=list(powers))

    def test_power_check_exception_wrapped_as_error_content(self):
        handler = mock.Mock()
        spec = self._spec(handler=handler)
        with patch("apps.ai.tools.base.has_power", side_effect=RuntimeError("db down")):
            result = spec.call(USER, {})
        self.assertTrue(result["isError"])
        self.assertIn("db down", result["content"][0]["text"])
        handler.assert_not_called()

    def test_denied_power_returns_error_content(self):
        with patch("apps.ai.tools.base.has_power", return_value=False):
            result = self._spec().call(USER, {})
        self.assertTrue(result["isError"])
        self.assertIn("quyền", result["content"][0]["text"])

    def test_allowed_power_calls_handler(self):
        with patch("apps.ai.tools.base.has_power", return_value=True):
            result = self._spec().call(USER, {})
        self.assertEqual(result, {"ok": True})


class ViewsWiringTests(SimpleTestCase):
    """Dispatcher + Header{1,2,3}DetailsView phải gắn HasHeaderPermission."""

    def test_dispatcher_enforces_header_permission(self):
        from rest_framework.permissions import IsAuthenticated

        from apps.systems.views import SystemDispatchView

        self.assertIn(HasHeaderPermission, SystemDispatchView.permission_classes)
        self.assertIn(IsAuthenticated, SystemDispatchView.permission_classes)

    def test_details_views_enforce_header_permission(self):
        from rest_framework.permissions import IsAuthenticated

        for n in (1, 2, 3):
            module = importlib.import_module(f"apps.systems.systems_details.{n}.views")
            view_cls = getattr(module, f"Header{n}DetailsView")
            self.assertEqual(view_cls.header_id, n, f"Header{n}DetailsView.header_id")
            self.assertIn(HasHeaderPermission, view_cls.permission_classes)
            self.assertIn(IsAuthenticated, view_cls.permission_classes)


class SignalWiringTests(SimpleTestCase):
    """apps.info.signals phải invalidate cache khi registration đổi (qua ready())."""

    @patch("apps.info.signals.invalidate_org_permission_cache")
    def test_header_registration_save_and_delete_invalidates_org(self, inv):
        post_save.send_robust(sender=HeaderRegistration, instance=SimpleNamespace(org_id=22), created=True)
        inv.assert_called_once_with(22)
        inv.reset_mock()
        post_delete.send_robust(sender=HeaderRegistration, instance=SimpleNamespace(org_id=22))
        inv.assert_called_once_with(22)

    @patch("apps.info.signals.invalidate_permission_cache")
    def test_user_registration_save_and_delete_invalidates_user(self, inv):
        post_save.send_robust(sender=UserHeaderRegistration, instance=SimpleNamespace(registered_by_id=7))
        inv.assert_called_once_with(7)
        inv.reset_mock()
        post_delete.send_robust(sender=UserHeaderRegistration, instance=SimpleNamespace(registered_by_id=7))
        inv.assert_called_once_with(7)
