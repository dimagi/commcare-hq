import json
from unittest.mock import patch

import pytest
from django.test import SimpleTestCase

from corehq.apps.export.export import (
    _log_export_generated,
    get_export_writer,
    write_export_instance,
)
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
from corehq.apps.export.models.new import (
    CaseExportInstanceFilters,
    FormExportInstanceFilters,
)
from corehq.util.files import TransientTempfile


def _make_case_export(case_type="patient"):
    return CaseExportInstance(
        domain="test-domain",
        case_type=case_type,
        name="Patient Cases",
        is_deidentified=False,
        export_format="xlsx",
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


def _make_form_export(xmlns="http://example.com/form", app_id=None, columns=None):
    return FormExportInstance(
        domain="test-domain",
        xmlns=xmlns,
        app_id=app_id,
        tables=[TableConfiguration(
            label="Forms",
            path=MAIN_TABLE,
            selected=True,
            columns=columns or [],
        )],
    )


def _logged_data(mock_logger):
    """Extract the dict that was logged from a mocked export_audit_logger."""
    mock_logger.info.assert_called_once()
    return json.loads(mock_logger.info.call_args[0][0])


class TestLogExportGenerated(SimpleTestCase):
    """Test the _log_export_generated helper directly."""

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_case_export_log_fields(self, mock_logger):
        export = _make_case_export()
        ctx = ExportLoggingContext(
            download_id="dl-abc",
            username="user@test.com",
            trigger="user_download",
            filters={"date_range": "2026-01-01 to 2026-03-01"},
            bulk=None,
        )
        _log_export_generated(export, row_count=42, logging_context=ctx)

        assert _logged_data(mock_logger) == {
            "event": "export_generated",
            "domain": "test-domain",
            "download_id": "dl-abc",
            "username": "user@test.com",
            "trigger": "user_download",
            "filters": {"date_range": "2026-01-01 to 2026-03-01"},
            "export_type": "case",
            "export_subtype": "patient",
            "export_id": None,
            "app_id": None,
            "name": "Patient Cases",
            "is_deidentified": False,
            "export_format": "xlsx",
            "row_count": 42,
            "columns": ["name", "dob"],
        }

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_form_export_subtype_and_app_id(self, mock_logger):
        export = _make_form_export(xmlns="http://example.com/form", app_id="app-abc123")
        _log_export_generated(export, row_count=10, logging_context=None)

        data = _logged_data(mock_logger)
        assert data["export_type"] == "form"
        assert data["export_subtype"] == "http://example.com/form"
        assert data["app_id"] == "app-abc123"

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_sms_export_no_subtype(self, mock_logger):
        export = SMSExportInstance(domain="test-domain", tables=[])
        _log_export_generated(export, row_count=5, logging_context=None)

        data = _logged_data(mock_logger)
        assert data["export_type"] == "sms"
        assert "export_subtype" not in data

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_bulk_info_included(self, mock_logger):
        export = _make_case_export()
        ctx = ExportLoggingContext(
            download_id=None, username=None, trigger=None,
            filters={}, bulk={"index": 2, "total": 3},
        )
        _log_export_generated(export, row_count=0, logging_context=ctx)

        assert _logged_data(mock_logger)["bulk"] == {"index": 2, "total": 3}

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_no_context_uses_none(self, mock_logger):
        export = _make_case_export()
        _log_export_generated(export, row_count=0, logging_context=None)

        data = _logged_data(mock_logger)
        assert data["download_id"] is None
        assert data["username"] is None
        assert data["trigger"] is None
        assert data["filters"] == {}
        assert "bulk" not in data

    @patch('corehq.apps.export.export.export_audit_logger')
    def test_only_selected_columns_from_selected_tables(self, mock_logger):
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

        assert _logged_data(mock_logger)["columns"] == ["name"]


class TestWriteExportInstanceLogging(SimpleTestCase):
    """Integration test: verify write_export_instance calls the logger."""

    def _run_write_export_instance(self, export, **kwargs):
        docs = [{"domain": "test-domain", "_id": "1", "form": {"q1": "val"}}]
        with TransientTempfile() as temp_path:
            writer = get_export_writer([export], temp_path)
            with writer.open([export]):
                write_export_instance(writer, export, docs, **kwargs)

    @patch('corehq.apps.export.export.export_audit_logger')
    @patch('corehq.apps.export.models.FormExportInstance.save')
    def test_logging_called_when_context_provided(self, mock_save, mock_logger):
        export = _make_form_export(columns=[
            ExportColumn(label="q1", item=ExportItem(path=[PathNode(name="q1")]), selected=True),
        ])
        ctx = ExportLoggingContext(
            download_id="dl-abc",
            username="user@test.com",
            trigger="user_download",
            filters={},
            bulk=None,
        )

        self._run_write_export_instance(export, logging_context=ctx)

        mock_logger.info.assert_called_once()

    @patch('corehq.apps.export.export.export_audit_logger')
    @patch('corehq.apps.export.models.FormExportInstance.save')
    def test_logging_called_even_without_context(self, mock_save, mock_logger):
        export = _make_form_export(columns=[
            ExportColumn(label="q1", item=ExportItem(path=[PathNode(name="q1")]), selected=True),
        ])

        self._run_write_export_instance(export)

        # Logging always fires (context fields are just None)
        mock_logger.info.assert_called_once()


class TestBuildFilterSummary:

    def test_none_returns_empty(self):
        assert build_filter_summary(None) == {}

    @pytest.mark.parametrize("field", [
        "can_access_all_locations",
        "show_project_data",
        "sharing_groups",
    ])
    def test_all_defaults_returns_all_fields(self, field):
        result = build_filter_summary(CaseExportInstanceFilters())
        assert field in result

    def test_non_default_values_included(self):
        filters = CaseExportInstanceFilters(users=["user1", "user2"])
        assert build_filter_summary(filters)["users"] == ["user1", "user2"]

    def test_form_filters_include_user_types(self):
        assert "user_types" in build_filter_summary(FormExportInstanceFilters())

    def test_doc_type_excluded(self):
        assert "doc_type" not in build_filter_summary(CaseExportInstanceFilters())
