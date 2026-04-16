from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.export.export import _log_export_generated, get_export_writer, write_export_instance
from corehq.apps.export.logging import ExportLoggingContext, build_filter_summary
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
from corehq.apps.export.models.new import CaseExportInstanceFilters, FormExportInstanceFilters
from corehq.util.files import TransientTempfile


def _make_case_export(case_type="patient"):
    return CaseExportInstance(
        domain="test-domain",
        case_type=case_type,
        tables=[TableConfiguration(
            label="Cases",
            path=MAIN_TABLE,
            selected=True,
            columns=[
                ExportColumn(label="name", item=ExportItem(path=[PathNode(name="name")]), selected=True),
                ExportColumn(label="dob", item=ExportItem(path=[PathNode(name="dob")]), selected=True),
                ExportColumn(label="hidden", item=ExportItem(path=[PathNode(name="hidden")]), selected=False),
            ],
        )],
    )


class TestLogExportGenerated(SimpleTestCase):
    """Test the _log_export_generated helper directly."""

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_case_export_log_fields(self, mock_logger):
        import json
        export = _make_case_export()
        ctx = ExportLoggingContext(
            download_id="dl-abc",
            username="user@test.com",
            trigger="user_download",
            filters={"date_range": "2026-01-01 to 2026-03-01"},
            bulk=None,
        )
        _log_export_generated(export, row_count=42, logging_context=ctx)

        mock_logger.info.assert_called_once()
        data = json.loads(mock_logger.info.call_args[0][0])
        self.assertEqual(data["event"], "export_generated")
        self.assertEqual(data["domain"], "test-domain")
        self.assertEqual(data["download_id"], "dl-abc")
        self.assertEqual(data["username"], "user@test.com")
        self.assertEqual(data["trigger"], "user_download")
        self.assertEqual(data["export_type"], "case")
        self.assertEqual(data["export_subtype"], "patient")
        self.assertIsNone(data["app_id"])
        self.assertEqual(data["row_count"], 42)
        self.assertEqual(data["columns"], ["name", "dob"])
        self.assertEqual(data["filters"], {"date_range": "2026-01-01 to 2026-03-01"})
        self.assertNotIn("bulk", data)

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_form_export_subtype_and_app_id(self, mock_logger):
        import json
        export = FormExportInstance(
            domain="test-domain",
            xmlns="http://example.com/form",
            app_id="app-abc123",
            tables=[TableConfiguration(label="Forms", path=MAIN_TABLE, selected=True, columns=[])],
        )
        _log_export_generated(export, row_count=10, logging_context=None)

        data = json.loads(mock_logger.info.call_args[0][0])
        self.assertEqual(data["export_type"], "form")
        self.assertEqual(data["export_subtype"], "http://example.com/form")
        self.assertEqual(data["app_id"], "app-abc123")

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_sms_export_no_subtype(self, mock_logger):
        import json
        export = SMSExportInstance(domain="test-domain", tables=[])
        _log_export_generated(export, row_count=5, logging_context=None)

        data = json.loads(mock_logger.info.call_args[0][0])
        self.assertEqual(data["export_type"], "sms")
        self.assertNotIn("export_subtype", data)

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_bulk_info_included(self, mock_logger):
        import json
        export = _make_case_export()
        ctx = ExportLoggingContext(
            download_id=None, username=None, trigger=None,
            filters={}, bulk={"index": 2, "total": 3},
        )
        _log_export_generated(export, row_count=0, logging_context=ctx)

        data = json.loads(mock_logger.info.call_args[0][0])
        self.assertEqual(data["bulk"], {"index": 2, "total": 3})

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_no_context_uses_none(self, mock_logger):
        import json
        export = _make_case_export()
        _log_export_generated(export, row_count=0, logging_context=None)

        data = json.loads(mock_logger.info.call_args[0][0])
        self.assertIsNone(data["download_id"])
        self.assertIsNone(data["username"])
        self.assertIsNone(data["trigger"])
        self.assertEqual(data["filters"], {})
        self.assertNotIn("bulk", data)

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_only_selected_columns_from_selected_tables(self, mock_logger):
        import json
        export = CaseExportInstance(
            domain="test-domain",
            case_type="patient",
            tables=[
                TableConfiguration(label="Main", path=MAIN_TABLE, selected=True, columns=[
                    ExportColumn(label="name", item=ExportItem(path=[PathNode(name="name")]), selected=True),
                    ExportColumn(label="hidden", item=ExportItem(path=[PathNode(name="x")]), selected=False),
                ]),
                TableConfiguration(label="Unselected", path=[PathNode(name="other")], selected=False, columns=[
                    ExportColumn(label="ignored", item=ExportItem(path=[PathNode(name="y")]), selected=True),
                ]),
            ],
        )
        _log_export_generated(export, row_count=0, logging_context=None)

        data = json.loads(mock_logger.info.call_args[0][0])
        self.assertEqual(data["columns"], ["name"])


class TestWriteExportInstanceLogging(SimpleTestCase):
    """Integration test: verify write_export_instance calls the logger."""

    @patch('corehq.apps.export.export.export_audit_logger')
    @patch('corehq.apps.export.models.FormExportInstance.save')
    def test_logging_called_when_context_provided(self, mock_save, mock_logger):
        export = FormExportInstance(
            domain="test-domain",
            xmlns="http://example.com/form",
            tables=[TableConfiguration(
                label="Forms",
                path=MAIN_TABLE,
                selected=True,
                columns=[
                    ExportColumn(label="q1", item=ExportItem(path=[PathNode(name="q1")]), selected=True),
                ],
            )],
        )
        docs = [{"domain": "test-domain", "_id": "1", "form": {"q1": "val"}}]
        ctx = ExportLoggingContext(
            download_id="dl-abc",
            username="user@test.com",
            trigger="user_download",
            filters={},
            bulk=None,
        )

        with TransientTempfile() as temp_path:
            writer = get_export_writer([export], temp_path)
            with writer.open([export]):
                write_export_instance(writer, export, docs, logging_context=ctx)

        mock_logger.info.assert_called_once()

    @patch('corehq.apps.export.export.export_audit_logger')
    @patch('corehq.apps.export.models.FormExportInstance.save')
    def test_logging_called_even_without_context(self, mock_save, mock_logger):
        export = FormExportInstance(
            domain="test-domain",
            xmlns="http://example.com/form",
            tables=[TableConfiguration(
                label="Forms",
                path=MAIN_TABLE,
                selected=True,
                columns=[
                    ExportColumn(label="q1", item=ExportItem(path=[PathNode(name="q1")]), selected=True),
                ],
            )],
        )
        docs = [{"domain": "test-domain", "_id": "1", "form": {"q1": "val"}}]

        with TransientTempfile() as temp_path:
            writer = get_export_writer([export], temp_path)
            with writer.open([export]):
                write_export_instance(writer, export, docs)

        # Logging always fires (context fields are just None)
        mock_logger.info.assert_called_once()


class TestBuildFilterSummary(SimpleTestCase):

    def test_none_returns_empty(self):
        self.assertEqual(build_filter_summary(None), {})

    def test_all_defaults_returns_all_fields(self):
        filters = CaseExportInstanceFilters()
        result = build_filter_summary(filters)
        self.assertIn("can_access_all_locations", result)
        self.assertIn("show_project_data", result)
        self.assertIn("sharing_groups", result)

    def test_non_default_values_included(self):
        filters = CaseExportInstanceFilters(users=["user1", "user2"])
        result = build_filter_summary(filters)
        self.assertEqual(result["users"], ["user1", "user2"])

    def test_form_filters_include_user_types(self):
        filters = FormExportInstanceFilters()
        result = build_filter_summary(filters)
        self.assertIn("user_types", result)

    def test_doc_type_excluded(self):
        filters = CaseExportInstanceFilters()
        result = build_filter_summary(filters)
        self.assertNotIn("doc_type", result)
