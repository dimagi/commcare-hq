from django.test import TestCase
from corehq.apps.userreports.models import ReportConfiguration
from corehq.apps.userreports.dbaccessors import get_report_configs_for_domain, \
    get_all_report_configs, get_number_of_report_configs_by_data_source


class DBAccessorsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_source_id = 'd36c7c934cb84725899cca9a0ef96e3a'
        cls.domain = 'userreport-dbaccessors'
        cls.report_configs = [
            ReportConfiguration(domain=cls.domain,
                                config_id=cls.data_source_id, title='A'),
            ReportConfiguration(domain=cls.domain,
                                config_id=cls.data_source_id, title='B'),
            ReportConfiguration(domain=cls.domain,
                                config_id='asabsdjf', title='C'),
            ReportConfiguration(domain='mallory',
                                config_id=cls.data_source_id, title='X'),
        ]
        ReportConfiguration.get_db().bulk_save(cls.report_configs)

    @classmethod
    def tearDownClass(cls):
        ReportConfiguration.get_db().bulk_delete(cls.report_configs)

    def test_get_number_of_report_configs_by_data_source(self):
        self.assertEqual(
            get_number_of_report_configs_by_data_source(
                self.domain, self.data_source_id),
            len([report_config for report_config in self.report_configs
                 if report_config.domain == self.domain
                 and report_config.config_id == self.data_source_id])
        )

    def test_get_all_report_configs(self):
        self.assertItemsEqual(
            [o.to_json() for o in get_all_report_configs()],
            [o.to_json() for o in self.report_configs]
        )

    def test_get_report_configs_for_domain(self):
        self.assertEqual(
            [o.to_json() for o in get_report_configs_for_domain(self.domain)],
            [report_config.to_json() for report_config
             in sorted(self.report_configs, key=lambda report: report.title)
             if report_config.domain == self.domain]
        )
