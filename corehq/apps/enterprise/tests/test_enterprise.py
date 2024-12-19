from django.test import SimpleTestCase, override_settings
from datetime import datetime
from freezegun import freeze_time
from unittest.mock import patch, MagicMock

from corehq.apps.enterprise.exceptions import TooMuchRequestedDataError
from corehq.apps.export.models.new import FormExportInstance
from corehq.apps.accounting.models import BillingAccount
from corehq.apps.domain.models import Domain
from corehq.apps.export.dbaccessors import ODataExportFetcher
from corehq.apps.enterprise.enterprise import (
    EnterpriseODataReport,
    EnterpriseFormReport,
)


@override_settings(BASE_ADDRESS='localhost:8000')
class EnterpriseODataReportTests(SimpleTestCase):
    def test_headers(self):
        report = self._create_report_for_domains()
        self.assertEqual(report.headers, [
            'Odata feeds used', 'Odata feeds available', 'Report Names', 'Number of rows',
            'Project Space Name', 'Project Name', 'Project URL'
        ])

    def test_total_number_display_odata_reports_across_enterprise(self):
        domain_one = self._create_domain(name='domain_one')
        domain_two = self._create_domain(name='domain_two')
        self.domain_to_export_map['domain_one'] = [
            self._create_export()
        ]
        self.domain_to_export_map['domain_two'] = [
            self._create_export(),
            self._create_export()
        ]

        report = self._create_report_for_domains(domain_one, domain_two)
        self.assertEqual(report.total_for_domain(domain_one), 1)
        self.assertEqual(report.total_for_domain(domain_two), 2)
        self.assertEqual(report.total, 3)

    def test_full_report_for_single_domain(self):
        domain_one = self._create_domain(name='domain_one', max_exports=10)
        self.domain_to_export_map['domain_one'] = [
            self._create_export(name='ExportOne', row_count=5),
            self._create_export(name='ExportTwo', row_count=7)
        ]

        report = self._create_report_for_domains(domain_one)
        self.assertEqual(report.rows, [
            [2, 10, None, 12, 'domain_one', None, 'http://localhost:8000/a/domain_one/settings/project/'],
            [None, None, 'ExportOne', 5],
            [None, None, 'ExportTwo', 7]
        ])

    def test_full_report_for_multiple_domains(self):
        domain_one = self._create_domain(name='domain_one', max_exports=25)
        domain_two = self._create_domain(name='domain_two', max_exports=50)

        self.domain_to_export_map['domain_one'] = [self._create_export(name='ExportOne', row_count=9)]
        self.domain_to_export_map['domain_two'] = [self._create_export(name='ExportTwo', row_count=15)]

        report = self._create_report_for_domains(domain_one, domain_two)

        self.assertEqual(report.rows, [
            [1, 25, None, 9, 'domain_one', None, 'http://localhost:8000/a/domain_one/settings/project/'],
            [None, None, 'ExportOne', 9],
            [1, 50, None, 15, 'domain_two', None, 'http://localhost:8000/a/domain_two/settings/project/'],
            [None, None, 'ExportTwo', 15]
        ])

    @patch.object(ODataExportFetcher, 'get_export_count')
    def test_report_replaces_row_count_with_error_when_too_many_exports(self, mock_export_count):
        mock_export_count.return_value = 151
        domain_one = self._create_domain(name='domain_one', max_exports=200)

        report = self._create_report_for_domains(domain_one)

        self.assertEqual(report.rows, [
            [151, 200, None,
            'ERROR: Too many exports. Please contact customer service',
            'domain_one', None, 'http://localhost:8000/a/domain_one/settings/project/']
        ])

    @patch.object(ODataExportFetcher, 'get_export_count')
    def test_no_exports_for_domain_shows_0_rowcount(self, mock_export_count):
        mock_export_count.return_value = 0
        domain_one = self._create_domain(name='domain_one', max_exports=25)

        report = self._create_report_for_domains(domain_one)

        self.assertEqual(report.rows, [
            [0, 25, None, 0, 'domain_one', None, 'http://localhost:8000/a/domain_one/settings/project/']
        ])

# setup / helpers

    def setUp(self):
        super().setUp()

        # NOTE: This convoluted patching is because JSON Object doesn't allow
        #  child properties/methods to be mocked out. This is a workaround, where
        #  the class method is getting mocked out instead
        form_patcher = patch.object(FormExportInstance, 'get_count',
            lambda self: self.mock_count if hasattr(self, 'mock_count') else 0)
        form_patcher.start()
        self.addCleanup(form_patcher.stop)

        self.domain_to_export_map = {}
        fetcher_patcher = patch.object(ODataExportFetcher, 'get_exports',
            lambda _, domain: self.domain_to_export_map[domain])
        fetcher_patcher.start()
        self.addCleanup(fetcher_patcher.stop)
        count_patcher = patch.object(ODataExportFetcher, 'get_export_count',
            lambda _, domain: len(self.domain_to_export_map[domain]))
        count_patcher.start()
        self.addCleanup(count_patcher.stop)

        self.billing_account = BillingAccount()
        self.next_id = 1

    def _create_export(self, name='TestExport', domain='TestDomain', row_count=10):
        export = FormExportInstance(_id=str(self.next_id), name=name, domain=domain, is_odata_config=True)
        self.next_id += 1
        export.mock_count = row_count
        return export

    def _create_domain(self, name='TestDomain', max_exports=10):
        return Domain(name=name, odata_feed_limit=max_exports)

    def _create_report_for_domains(self, *domains):
        report = EnterpriseODataReport(self.billing_account, None)
        report.domains = MagicMock(return_value=domains)
        return report


@freeze_time(datetime(month=10, day=1, year=2024))
class EnterpriseFormReportTests(SimpleTestCase):
    def setUp(self):
        super().setUp()

        self.billing_account = BillingAccount()

    def test_constructor_with_no_datespan_defaults_to_last_30_days(self):
        report = EnterpriseFormReport(self.billing_account, None)

        self.assertEqual(report.datespan.startdate, datetime(month=9, day=1, year=2024))
        self.assertEqual(report.datespan.enddate, datetime(month=10, day=1, year=2024))

    def test_constructor_with_provided_dates_uses_that_datespan(self):
        start_date = datetime(month=11, day=25, year=2023)
        end_date = datetime(month=12, day=15, year=2023)
        report = EnterpriseFormReport(self.billing_account, None, start_date=start_date, end_date=end_date)

        self.assertEqual(report.datespan.startdate, start_date)
        self.assertEqual(report.datespan.enddate, end_date)

    def test_constructor_with_only_end_date_uses_default_num_days(self):
        end_date = datetime(month=10, day=1, year=2020)
        report = EnterpriseFormReport(self.billing_account, None, end_date=end_date)

        self.assertEqual(report.datespan.startdate, datetime(month=9, day=1, year=2020))
        self.assertEqual(report.datespan.enddate, end_date)

    def test_constructor_with_only_end_date_uses_num_days(self):
        end_date = datetime(month=10, day=1, year=2020)
        report = EnterpriseFormReport(self.billing_account, None, end_date=end_date, num_days=10)

        self.assertEqual(report.datespan.startdate, datetime(month=9, day=21, year=2020))
        self.assertEqual(report.datespan.enddate, end_date)

    def test_specifying_timespan_greater_than_90_days_throws_error(self):
        end_date = datetime(month=10, day=1, year=2020)
        with self.assertRaises(TooMuchRequestedDataError):
            EnterpriseFormReport(self.billing_account, None, end_date=end_date, num_days=91)

    def test_specifying_timespans_up_to_90_days_works(self):
        end_date = datetime(month=10, day=1, year=2020)
        EnterpriseFormReport(self.billing_account, None, end_date=end_date, num_days=90)
