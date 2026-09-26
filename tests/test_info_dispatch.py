"""
Test dispatcher `POST /api/v1/info/dispatch` — endpoint DUY NHẤT của app info,
thay thế toàn bộ CRUD cũ dùng PUT / PATCH / DELETE (xem apps/info/dispatch.py).

Không cần DB: request giả (APIRequestFactory + force_authenticate) và patch
truy vấn/model; model instance dùng để test serializer là instance CHƯA lưu
(không chạm database).

Chạy: python -m pytest tests/test_info_dispatch.py -q
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.info import dispatch
from apps.info.models import GroupHeader
from apps.info.serializers import InfoDispatchSerializer
from apps.info.views import InfoDispatchView

USER = SimpleNamespace(id=7, org_id=22, is_authenticated=True)


def make_request(payload, user=USER):
    """Gọi thẳng view (đã xác thực) — không qua middleware/urls."""
    request = APIRequestFactory().post("/api/v1/info/dispatch", payload, format="json")
    if user is not None:
        force_authenticate(request, user=user)
    return InfoDispatchView.as_view()(request)


def unsaved_group():
    """Model instance CHƯA lưu (an toàn trong SimpleTestCase)."""
    return GroupHeader(pk=1, sort=1, is_use=True, group_vi="G", group_en="G", group_kr="G")


class InfoDispatchSerializerTests(SimpleTestCase):
    """Validate payload dispatcher."""

    def test_resource_and_action_are_required(self):
        serializer = InfoDispatchSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("resource", serializer.errors)
        self.assertIn("action", serializer.errors)

    def test_unknown_resource_or_action_rejected(self):
        self.assertFalse(InfoDispatchSerializer(data={"resource": "nope", "action": "list"}).is_valid())
        self.assertFalse(InfoDispatchSerializer(data={"resource": "group_headers", "action": "patch"}).is_valid())

    def test_id_required_for_item_actions(self):
        for action in ("retrieve", "update", "delete"):
            serializer = InfoDispatchSerializer(data={"resource": "group_headers", "action": action})
            self.assertFalse(serializer.is_valid(), action)
            self.assertIn("id", serializer.errors)

    def test_data_required_for_create_and_reorder(self):
        for action in ("create", "reorder"):
            serializer = InfoDispatchSerializer(data={"resource": "group_headers", "action": action})
            self.assertFalse(serializer.is_valid(), action)
            self.assertIn("data", serializer.errors)

    def test_params_must_be_object(self):
        serializer = InfoDispatchSerializer(data={"resource": "headers", "action": "structure", "params": "x"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("params", serializer.errors)

    def test_valid_payload(self):
        serializer = InfoDispatchSerializer(
            data={"resource": "group_headers", "action": "update", "id": 3, "data": {"partial": True, "sort": 2}}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_json_string_data_and_params_are_parsed(self):
        """Multipart (FE gửi kèm file) truyền data/params dạng chuỗi JSON."""
        serializer = InfoDispatchSerializer(
            data={
                "resource": "headers",
                "action": "structure",
                "params": '{"scope": "registered"}',
                "data": '{"partial": true}',
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["params"], {"scope": "registered"})
        self.assertEqual(serializer.validated_data["data"], {"partial": True})

    def test_empty_string_params_becomes_none(self):
        serializer = InfoDispatchSerializer(data={"resource": "headers", "action": "structure", "params": ""})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIsNone(serializer.validated_data["params"])

    def test_invalid_json_string_is_rejected(self):
        serializer = InfoDispatchSerializer(
            data={"resource": "headers", "action": "structure", "params": "{khong-phai-json}"}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("params", serializer.errors)


class RequiresWritePermissionTests(SimpleTestCase):
    """Action nào cần quyền ghi cấu hình."""

    def test_write_actions_require_permission(self):
        for action in dispatch.WRITE_ACTIONS:
            self.assertTrue(dispatch.requires_write_permission("group_headers", action), action)

    def test_read_actions_do_not_require_permission(self):
        self.assertFalse(dispatch.requires_write_permission("group_headers", "list"))
        self.assertFalse(dispatch.requires_write_permission("group_headers", "retrieve"))
        self.assertFalse(dispatch.requires_write_permission("headers", "structure", {"scope": "registered"}))

    def test_full_structure_scope_requires_permission(self):
        self.assertTrue(dispatch.requires_write_permission("headers", "structure", {"scope": "all"}))


class DispatcherHelpersTests(SimpleTestCase):
    """Helper thuần: pagination, ordering whitelist, whitelist field ghi."""

    def test_paginate_clamps_per_page(self):
        queryset = GroupHeader.objects.none()
        _items, meta = dispatch._paginate(queryset, {"per_page": 9999})
        self.assertEqual(meta["per_page"], dispatch.MAX_PER_PAGE)
        _items, meta = dispatch._paginate(queryset, {"per_page": "abc"})
        self.assertEqual(meta["per_page"], dispatch.DEFAULT_PER_PAGE)

    def test_ordering_whitelist_blocks_unknown_fields(self):
        config = dispatch.RESOURCES["group_headers"]
        self.assertEqual(dispatch._clean_ordering("-sort", config), ["-sort"])
        self.assertEqual(dispatch._clean_ordering("password", config), list(config["order_by"]))

    def test_write_data_whitelist(self):
        config = dispatch.RESOURCES["group_headers"]
        clean = dispatch._clean_write_data(config, {"group_vi": "A", "id": 99, "is_use": False})
        self.assertEqual(clean, {"group_vi": "A", "is_use": False})
        self.assertIsNone(dispatch._clean_write_data(config, {"id": 99}))
        self.assertIsNone(dispatch._clean_write_data(config, "khong-phai-object"))

    def test_coerce_bool(self):
        for truthy in (True, 1, "true", "1", "yes"):
            self.assertTrue(dispatch._coerce_bool(truthy), truthy)
        for falsy in (False, 0, "false", "0", "", None):
            self.assertFalse(dispatch._coerce_bool(falsy), falsy)


class DispatcherRoutingTests(SimpleTestCase):
    """Action nào đi tới handler nào / lỗi nào."""

    PAGE_META = {"page": 1, "per_page": 20, "total": 0, "total_pages": 1, "has_next": False, "has_previous": False}

    def test_unknown_resource(self):
        response = dispatch.handle("khong_co", "list", USER)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])

    def test_headers_resource_only_supports_structure(self):
        response = dispatch.handle("headers", "list", USER)
        self.assertEqual(response.status_code, 400)

    def test_structure_registered_uses_registered_service(self):
        with patch("apps.info.dispatch.services.get_registered_structure", return_value=[{"group_id": 1}]) as service:
            response = dispatch.handle("headers", "structure", USER, params={"scope": "registered"}, language="vi")
        service.assert_called_once_with(USER, "vi")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"], [{"group_id": 1}])
        self.assertEqual(response.data["meta"]["scope"], "registered")

    def test_structure_full_scope_uses_full_service(self):
        with patch("apps.info.dispatch.services.get_full_structure", return_value=[]) as service:
            response = dispatch.handle("headers", "structure", USER, params={"scope": "all"}, language="en")
        service.assert_called_once_with("en")
        self.assertEqual(response.status_code, 200)

    def test_structure_invalid_scope(self):
        response = dispatch.handle("headers", "structure", USER, params={"scope": "khong-co"})
        self.assertEqual(response.status_code, 400)

    def test_list_returns_paginated_envelope(self):
        with patch.object(dispatch, "_paginate", return_value=([], self.PAGE_META)):
            response = dispatch.handle("group_headers", "list", USER)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"], [])
        self.assertEqual(response.data["meta"]["total"], 0)

    def test_list_with_search_and_filter_does_not_break(self):
        with patch.object(dispatch, "_paginate", return_value=([], self.PAGE_META)), patch(
            "apps.info.dispatch.get_user_permitted_header_ids", return_value=[1, 2]
        ):
            response = dispatch.handle("system_headers", "list", USER, params={"search": "kcs", "is_use": "true"})
        self.assertEqual(response.status_code, 200)

    def test_retrieve_missing_object_returns_404(self):
        with patch.object(dispatch, "_get_object", return_value=None):
            response = dispatch.handle("group_headers", "retrieve", USER, item_id=99)
        self.assertEqual(response.status_code, 404)

    def test_retrieve_returns_instance(self):
        with patch.object(dispatch, "_get_object", return_value=unsaved_group()):
            response = dispatch.handle("group_headers", "retrieve", USER, item_id=1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["id"], 1)

    def test_system_header_retrieve_respects_t1_permission(self):
        with patch.object(dispatch, "_get_object", return_value=unsaved_group()), patch(
            "apps.info.dispatch.get_user_permitted_header_ids", return_value=[]
        ):
            response = dispatch.handle("system_headers", "retrieve", USER, item_id=1)
        self.assertEqual(response.status_code, 403)

    def test_update_missing_object_returns_404(self):
        with patch.object(dispatch, "_get_object", return_value=None):
            response = dispatch.handle("group_headers", "update", USER, item_id=99, data={"group_vi": "A"})
        self.assertEqual(response.status_code, 404)

    def test_update_without_writable_field_returns_400(self):
        with patch.object(dispatch, "_get_object", return_value=unsaved_group()):
            response = dispatch.handle("group_headers", "update", USER, item_id=1, data={"id": 5})
        self.assertEqual(response.status_code, 400)

    def test_create_without_writable_field_returns_400(self):
        response = dispatch.handle("group_headers", "create", USER, data={"khong_co": 1})
        self.assertEqual(response.status_code, 400)

    def test_create_success_returns_201(self):
        fake_serializer = MagicMock()
        fake_serializer.return_value.is_valid.return_value = True
        fake_serializer.return_value.save.return_value = unsaved_group()
        fake_serializer.return_value.data = {"id": 1, "group_vi": "G"}
        with patch.dict(dispatch.RESOURCES["group_headers"], {"serializer": fake_serializer}):
            response = dispatch.handle("group_headers", "create", USER, data={"group_vi": "G"})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])

    def test_update_partial_flag_is_forwarded(self):
        fake_serializer = MagicMock()
        fake_serializer.return_value.is_valid.return_value = True
        fake_serializer.return_value.data = {"id": 1}
        with patch.object(dispatch, "_get_object", return_value=unsaved_group()), patch.dict(
            dispatch.RESOURCES["group_headers"], {"serializer": fake_serializer}
        ):
            response = dispatch.handle("group_headers", "update", USER, item_id=1, data={"group_vi": "A", "partial": True})
            _args, kwargs = fake_serializer.call_args
        self.assertEqual(response.status_code, 200)
        self.assertTrue(kwargs["partial"])
        self.assertEqual(kwargs["data"], {"group_vi": "A"})

    def test_delete_success_returns_envelope_not_204(self):
        instance = MagicMock()
        instance.pk = 5
        with patch.object(dispatch, "_get_object", return_value=instance):
            response = dispatch.handle("group_headers", "delete", USER, item_id=5)
        instance.delete.assert_called_once()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["deleted"])

    def test_reorder_requires_non_empty_array(self):
        self.assertEqual(dispatch.handle("group_headers", "reorder", USER, data={"order": []}).status_code, 400)
        self.assertEqual(dispatch.handle("group_headers", "reorder", USER, data={"order": ["a"]}).status_code, 400)

    def test_reorder_updates_sort_in_order(self):
        manager = MagicMock()
        manager.filter.return_value.update.return_value = 1
        # transaction.atomic() cần kết nối DB → patch để test không chạm database
        with patch.object(GroupHeader, "objects", manager), patch("apps.info.dispatch.transaction.atomic"):
            response = dispatch.handle("group_headers", "reorder", USER, data={"order": [3, 1, 2]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"], {"requested": 3, "updated": 3})
        self.assertEqual(manager.filter.call_args_list[0].kwargs, {"pk": 3})
        self.assertEqual(manager.filter.return_value.update.call_args.kwargs, {"sort": 3})


class InfoDispatchViewTests(SimpleTestCase):
    """Endpoint thật: 401 / 400 / 403 / 200."""

    def test_requires_authentication(self):
        response = make_request({"resource": "group_headers", "action": "list"}, user=None)
        self.assertEqual(response.status_code, 401)

    def test_invalid_payload_returns_400(self):
        response = make_request({"resource": "sai", "action": "sai"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertIsNotNone(response.data["errors"])

    @override_settings(INFO_DISPATCH_WRITE_ENABLED=False)
    def test_write_disabled_returns_403(self):
        response = make_request({"resource": "group_headers", "action": "create", "data": {"group_vi": "A"}})
        self.assertEqual(response.status_code, 403)

    @override_settings(INFO_DISPATCH_WRITE_ENABLED=True, INFO_DISPATCH_ALLOWED_POWERS=["manage_header"])
    def test_write_denied_when_user_has_no_power(self):
        with patch("apps.ai.tools.base.has_power", return_value=False):
            response = make_request({"resource": "group_headers", "action": "create", "data": {"group_vi": "A"}})
        self.assertEqual(response.status_code, 403)

    def test_full_structure_requires_write_power(self):
        with patch("apps.info.dispatch.services.get_full_structure", return_value=[]) as service:
            response = make_request({"resource": "headers", "action": "structure", "params": {"scope": "all"}})
        self.assertEqual(response.status_code, 403)
        service.assert_not_called()

    def test_structure_success(self):
        with patch("apps.info.dispatch.services.get_registered_structure", return_value=[{"group_id": 1}]):
            response = make_request({"resource": "headers", "action": "structure", "params": {"scope": "registered"}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"], [{"group_id": 1}])

    def test_multipart_json_string_params_are_parsed(self):
        """FE gửi kèm file → multipart: `params` là JSON string (xem build_form_data)."""
        request = APIRequestFactory().post(
            "/api/v1/info/dispatch",
            {"resource": "headers", "action": "structure", "params": '{"scope": "registered"}'},
        )
        force_authenticate(request, user=USER)
        with patch("apps.info.dispatch.services.get_registered_structure", return_value=[]):
            response = InfoDispatchView.as_view()(request)
        self.assertEqual(response.status_code, 200)


