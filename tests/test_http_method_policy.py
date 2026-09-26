"""
Test chính sách HTTP method: API CHỈ dùng GET / POST / OPTIONS.

Kiểm tra 3 lớp bảo vệ (xem ``libs/http_policy.py``):

    1. ``MethodPolicyMiddleware`` → 405 + envelope cho PUT/PATCH/DELETE trên /api/.
    2. ``PostOnlyRouter`` không sinh route PUT/PATCH/DELETE (chỉ POST).
    3. ``PostOnlyModelViewSet`` / ``PostOnlyUpdateMixin`` khai http_method_names.

Chạy: python -m pytest tests/test_http_method_policy.py -q
"""

from django.test import SimpleTestCase, override_settings

from libs.http_policy import ALLOWED_METHODS, is_method_allowed, is_protected_path
from libs.routers import PostOnlyRouter
from libs.viewsets import PostOnlyModelViewSet, PostOnlyUpdateMixin, _is_partial_request


class HttpPolicyUnitTests(SimpleTestCase):
    """Hằng số/helper của policy."""

    def test_allowed_methods(self):
        self.assertEqual(ALLOWED_METHODS, frozenset({"GET", "POST", "OPTIONS"}))
        for method in ("GET", "POST", "OPTIONS", "get", "post", "options"):
            self.assertTrue(is_method_allowed(method), method)
        for method in ("PUT", "PATCH", "DELETE", "HEAD", "", None):
            self.assertFalse(is_method_allowed(method), method)

    def test_protected_paths(self):
        self.assertTrue(is_protected_path("/api/v1/info/dispatch"))
        self.assertTrue(is_protected_path("/api/v1/anything"))
        # Tài liệu API dùng method riêng của DRF → không chặn
        self.assertFalse(is_protected_path("/api/docs/"))
        self.assertFalse(is_protected_path("/api/schema/"))
        self.assertFalse(is_protected_path("/admin/login/"))
        self.assertFalse(is_protected_path("/static/app.js"))


class MethodPolicyMiddlewareTests(SimpleTestCase):
    """Lớp 1 — middleware trả 405 + envelope."""

    def _forbidden(self, method, path="/api/v1/info/dispatch"):
        return getattr(self.client, method)(path, data="{}", content_type="application/json")

    def test_put_returns_405_envelope(self):
        response = self._forbidden("put")
        self.assertEqual(response.status_code, 405)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIsNone(body["data"])
        self.assertEqual(body["meta"]["status_code"], 405)
        self.assertIn("PUT", body["message"])
        self.assertIn("POST", body["errors"]["allowed_methods"])
        self.assertEqual(response["Allow"], "GET, POST, OPTIONS")

    def test_patch_and_delete_return_405(self):
        for method in ("patch", "delete"):
            response = self._forbidden(method)
            self.assertEqual(response.status_code, 405, method)
            self.assertEqual(response["Allow"], "GET, POST, OPTIONS")

    def test_get_is_never_blocked_by_policy(self):
        # GET /api/v1/accounts/auth/me không token → 401 (không phải 405)
        response = self.client.get("/api/v1/accounts/auth/me")
        self.assertNotEqual(response.status_code, 405)

    def test_non_api_paths_are_ignored(self):
        response = self.client.put("/admin/login/")
        self.assertNotEqual(response.status_code, 405)

    @override_settings(ENFORCE_HTTP_METHOD_POLICY=False)
    def test_policy_can_be_disabled_by_setting(self):
        response = self._forbidden("put")
        self.assertNotEqual(response.status_code, 405)


class PostOnlyRouterTests(SimpleTestCase):
    """Lớp 2 — router chỉ sinh GET/POST."""

    def _urls(self):
        router = PostOnlyRouter(trailing_slash=False)
        router.register("things", PostOnlyModelViewSet, basename="thing")
        # DRF gắn mapping HTTP method → action lên view function qua `.actions`
        return {url.name: getattr(url.callback, "actions", {}) for url in router.urls}

    def test_collection_and_detail_mapping(self):
        urls = self._urls()
        self.assertEqual(urls["thing-list"], {"get": "list", "post": "create"})
        self.assertEqual(urls["thing-detail"], {"get": "retrieve"})

    def test_update_and_delete_are_post_routes(self):
        urls = self._urls()
        self.assertEqual(urls["thing-update"], {"post": "update"})
        self.assertEqual(urls["thing-delete"], {"post": "destroy"})

    def test_no_put_patch_delete_anywhere(self):
        for name, method_map in self._urls().items():
            self.assertTrue(set(method_map) <= {"get", "post"}, f"{name}: {method_map}")


class PostOnlyViewSetTests(SimpleTestCase):
    """Lớp 2 — viewset/mixin."""

    def test_viewset_only_allows_get_post_options(self):
        self.assertEqual(PostOnlyModelViewSet.http_method_names, ["get", "post", "options"])

    def test_partial_flag_replaces_patch(self):
        class Request:
            def __init__(self, data):
                self.data = data

        self.assertFalse(_is_partial_request(Request({})))
        for truthy in (True, 1, "true", "TRUE", "1", "yes"):
            self.assertTrue(_is_partial_request(Request({"partial": truthy})), truthy)
        for falsy in (False, 0, "false", "0", "", None):
            self.assertFalse(_is_partial_request(Request({"partial": falsy})), falsy)

    def test_mixin_sets_partial_kwarg(self):
        class Stub:
            captured = None

            def update(self, request, *args, **kwargs):  # noqa: ARG002
                Stub.captured = kwargs.get("partial")

        class DummyView(PostOnlyUpdateMixin, Stub):
            pass

        class Request:
            data = {"partial": True}

        DummyView().update(Request())
        self.assertTrue(Stub.captured)
