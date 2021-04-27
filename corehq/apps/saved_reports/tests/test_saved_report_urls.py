from django.test import TestCase

from corehq.apps.saved_reports.models import ReportConfig
from corehq.apps.userreports.reports.view import ConfigurableReportView


class SavedReportURLTest(TestCase):

    def test_saved_standard_report_returns_query_string_with_filters(self):
        report_config = ReportConfig.wrap({
            "domain": 'saved-report-tests',
            "report_slug": "worker_activity",
            "owner_id": '0123456789',
            "report_type": "project_report",
            "filters": {
                "date-start": "2020-01-01",
                "date-end": "2020-12-31"
            }
        })
        report_config._id = 'abc123'

        query = report_config.query_string

        expected_query = 'config_id=abc123&date-start=2020-01-01&date-end=2020-12-31'
        self.assertEqual(query, expected_query)

    def test_saved_ucr_returns_query_string_without_filters(self):
        report_config = ReportConfig.wrap({
            "domain": 'saved-report-tests',
            "report_slug": "worker_activity",
            "owner_id": '0123456789',
            "report_type": ConfigurableReportView.prefix,
            "filters": {
                "date-start": "2020-01-01",
                "date-end": "2020-12-31"
            }
        })
        report_config._id = 'abc123'

        query = report_config.query_string

        expected_query = 'config_id=abc123'
        self.assertEqual(expected_query, query)
