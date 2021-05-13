from datetime import date

from django.test import TestCase

from corehq.apps.saved_reports.models import ReportConfig
from corehq.apps.userreports.reports.view import ConfigurableReportView


class SavedReportModelTest(TestCase):

    def test_saved_report_serialized_filters(self):
        report_config = ReportConfig.wrap({
            "domain": 'saved-report-tests',
            "report_slug": "worker_activity",
            "owner_id": '0123456789',
            "report_type": ConfigurableReportView.prefix,
            "filters": {
                "date-start": "2020-01-01",
                "date-end": "2020-12-31",
                "test-filter": "test"
            }
        })
        report_config._id = 'abc123'

        self.assertEqual(date, type(report_config.filters['date-start']))
        self.assertEqual(date, type(report_config.filters['date-end']))

        filters = report_config.serialized_filters

        expected_filters = {
            "date-start": "2020-01-01",
            "date-end": "2020-12-31",
            "test-filter": "test"
        }
        self.assertEqual(filters, expected_filters)
