from urllib.parse import urlencode

from django.test import TestCase

from corehq.apps.saved_reports.models import ReportConfig
from corehq.apps.userreports.reports.view import ConfigurableReportView


class SavedReportTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(SavedReportTest, cls).setUpClass()
        cls.domain = 'saved-report-tests'

    @classmethod
    def tearDownClass(cls):
        super(SavedReportTest, cls).tearDownClass()

    def tearDown(self):
        self.saved_report_config.delete()
        super(SavedReportTest, self).tearDown()

    def _create_saved_report(self, configurable=False):
        domain = self.domain
        report_config = ReportConfig.wrap({
            "date_range": "last30",
            "days": 30,
            "domain": domain,
            "report_slug": "worker_activity",
            "owner_id": '0123456789',
            "report_type": ConfigurableReportView.prefix if configurable else "project_report"
        })
        report_config.save()
        return report_config

    def test_standard_saved_report_query_string(self):
        self.saved_report_config = self._create_saved_report()

        actual_query = self.saved_report_config.query_string

        params = {'config_id': self.saved_report_config._id}
        params.update(self.saved_report_config.filters)
        params.update(self.saved_report_config.get_date_range())
        expected_query = urlencode(params)
        self.assertEqual(expected_query, actual_query)

    def test_ucr_saved_report_query_string_only_contains_config_id(self):
        self.saved_report_config = self._create_saved_report(configurable=True)

        actual_query = self.saved_report_config.query_string

        params = {'config_id': self.saved_report_config._id}
        expected_query = urlencode(params)
        self.assertEqual(expected_query, actual_query)
