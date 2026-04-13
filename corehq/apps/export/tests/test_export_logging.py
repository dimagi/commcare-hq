from django.test import SimpleTestCase

from corehq.apps.export.logging import (
    ExportLoggingContext,
    build_export_log_data,
    build_filter_summary,
)
from corehq.apps.export.models import (
    MAIN_TABLE,
    CaseExportInstance,
    ExportColumn,
    ExportItem,
    FormExportInstance,
    PathNode,
    SMSExportInstance,
    TableConfiguration,
)
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


class TestBuildExportLogData(SimpleTestCase):

    def _make_case_export(self, case_type="patient", columns=None):
        columns = columns or [
            ExportColumn(label="name", item=ExportItem(path=[PathNode(name="name")]), selected=True),
            ExportColumn(label="dob", item=ExportItem(path=[PathNode(name="dob")]), selected=True),
            ExportColumn(label="hidden", item=ExportItem(path=[PathNode(name="hidden")]), selected=False),
        ]
        return CaseExportInstance(
            domain="test-domain",
            case_type=case_type,
            tables=[TableConfiguration(
                label="Cases",
                path=MAIN_TABLE,
                selected=True,
                columns=columns,
            )],
        )

    def _make_form_export(self, xmlns="http://example.com/form"):
        return FormExportInstance(
            domain="test-domain",
            xmlns=xmlns,
            tables=[TableConfiguration(
                label="Forms",
                path=MAIN_TABLE,
                selected=True,
                columns=[
                    ExportColumn(label="q1", item=ExportItem(path=[PathNode(name="q1")]), selected=True),
                ],
            )],
        )

    def _make_context(self, **overrides):
        defaults = {
            "download_id": "dl-test123",
            "username": "testuser@example.com",
            "trigger": "user_download",
            "filters": {"active": {}, "default": {}},
        }
        defaults.update(overrides)
        return ExportLoggingContext(**defaults)

    def test_case_export_fields(self):
        export = self._make_case_export()
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=42)

        self.assertEqual(data["event"], "export_generated")
        self.assertEqual(data["domain"], "test-domain")
        self.assertEqual(data["download_id"], "dl-test123")
        self.assertEqual(data["username"], "testuser@example.com")
        self.assertEqual(data["trigger"], "user_download")
        self.assertEqual(data["export_type"], "case")
        self.assertEqual(data["export_subtype"], "patient")
        self.assertEqual(data["row_count"], 42)
        self.assertEqual(data["columns"], ["name", "dob"])
        self.assertNotIn("bulk", data)

    def test_form_export_subtype_is_xmlns(self):
        export = self._make_form_export(xmlns="http://example.com/myform")
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=10)

        self.assertEqual(data["export_type"], "form")
        self.assertEqual(data["export_subtype"], "http://example.com/myform")

    def test_sms_export_no_subtype(self):
        export = SMSExportInstance(domain="test-domain", tables=[])
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=5)

        self.assertEqual(data["export_type"], "sms")
        self.assertNotIn("export_subtype", data)

    def test_only_selected_columns_included(self):
        export = self._make_case_export()
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=0)

        self.assertIn("name", data["columns"])
        self.assertIn("dob", data["columns"])
        self.assertNotIn("hidden", data["columns"])

    def test_columns_from_multiple_selected_tables(self):
        export = CaseExportInstance(
            domain="test-domain",
            case_type="patient",
            tables=[
                TableConfiguration(
                    label="Main",
                    path=MAIN_TABLE,
                    selected=True,
                    columns=[
                        ExportColumn(label="name", item=ExportItem(path=[PathNode(name="name")]), selected=True),
                    ],
                ),
                TableConfiguration(
                    label="History",
                    path=[PathNode(name="history")],
                    selected=True,
                    columns=[
                        ExportColumn(
                            label="action",
                            item=ExportItem(path=[PathNode(name="action")]),
                            selected=True,
                        ),
                    ],
                ),
                TableConfiguration(
                    label="Unselected",
                    path=[PathNode(name="other")],
                    selected=False,
                    columns=[
                        ExportColumn(
                            label="ignored",
                            item=ExportItem(path=[PathNode(name="ignored")]),
                            selected=True,
                        ),
                    ],
                ),
            ],
        )
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=0)

        self.assertEqual(data["columns"], ["name", "action"])

    def test_bulk_info_included(self):
        export = self._make_case_export()
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=0, bulk={"index": 2, "total": 3})

        self.assertEqual(data["bulk"], {"index": 2, "total": 3})

    def test_bulk_omitted_when_none(self):
        export = self._make_case_export()
        ctx = self._make_context()
        data = build_export_log_data(export, ctx, row_count=0, bulk=None)

        self.assertNotIn("bulk", data)

    def test_none_context_still_works(self):
        export = self._make_case_export()
        data = build_export_log_data(export, None, row_count=10)

        self.assertEqual(data["event"], "export_generated")
        self.assertIsNone(data["download_id"])
        self.assertIsNone(data["username"])
        self.assertIsNone(data["trigger"])
        self.assertEqual(data["filters"], {"active": {}, "default": {}})
