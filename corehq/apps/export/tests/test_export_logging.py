from django.test import SimpleTestCase

from corehq.apps.export.logging import ExportLoggingContext, build_filter_summary
from corehq.apps.export.models.new import (
    CaseExportInstanceFilters,
    FormExportInstanceFilters,
)


class TestExportLoggingContext(SimpleTestCase):

    def test_construction_with_named_args(self):
        ctx = ExportLoggingContext(
            download_id="dl-abc123",
            username="user@example.com",
            trigger="user_download",
            filters={"active": {}, "default": {}},
        )
        self.assertEqual(ctx.download_id, "dl-abc123")
        self.assertEqual(ctx.username, "user@example.com")
        self.assertEqual(ctx.trigger, "user_download")
        self.assertEqual(ctx.filters, {"active": {}, "default": {}})

    def test_none_fields_for_rebuilds(self):
        ctx = ExportLoggingContext(
            download_id=None,
            username=None,
            trigger="scheduled_rebuild",
            filters={"active": {}, "default": {}},
        )
        self.assertIsNone(ctx.download_id)
        self.assertIsNone(ctx.username)


class TestBuildFilterSummary(SimpleTestCase):

    def test_all_defaults_case_filters(self):
        filters = CaseExportInstanceFilters()
        result = build_filter_summary(filters)
        self.assertEqual(result["active"], {})
        self.assertEqual(result["default"], {
            "can_access_all_locations": True,
            "accessible_location_ids": [],
            "locations": [],
            "date_period": None,
            "users": [],
            "reporting_groups": [],
            "user_types": [],
            "sharing_groups": [],
            "show_all_data": None,       # BooleanProperty() with no default returns None
            "show_project_data": True,
            "show_deactivated_data": None,  # BooleanProperty() with no default returns None
        })

    def test_non_default_values_go_to_active(self):
        filters = CaseExportInstanceFilters(
            show_all_data=True,
            users=["user1", "user2"],
        )
        result = build_filter_summary(filters)
        self.assertIn("show_all_data", result["active"])
        self.assertEqual(result["active"]["show_all_data"], True)
        self.assertIn("users", result["active"])
        self.assertEqual(result["active"]["users"], ["user1", "user2"])
        self.assertNotIn("show_all_data", result["default"])
        self.assertNotIn("users", result["default"])

    def test_form_filters_default_user_types(self):
        """FormExportInstanceFilters has a non-empty default for user_types"""
        filters = FormExportInstanceFilters()
        result = build_filter_summary(filters)
        # user_types default is [0, 1] (ACTIVE, DEACTIVATED) — should be in default
        self.assertIn("user_types", result["default"])

    def test_form_filters_non_default_user_types(self):
        filters = FormExportInstanceFilters(user_types=[0])
        result = build_filter_summary(filters)
        self.assertIn("user_types", result["active"])
        self.assertEqual(result["active"]["user_types"], [0])

    def test_none_filters_returns_empty(self):
        result = build_filter_summary(None)
        self.assertEqual(result, {"active": {}, "default": {}})
