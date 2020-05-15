from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.tests.utils import (
    get_sample_report_config,
    get_sample_data_source,
)

from corehq.apps.linked_domain.ucr import create_ucr_link
from corehq.apps.linked_domain.models import LinkedReportIDMap
from corehq.apps.userreports.models import DataSourceConfiguration, ReportConfiguration


class TestLinkedUCR(BaseLinkedAppsTest):
    def setUp(self):
        super().setUp()

        self.data_source = get_sample_data_source()
        self.data_source.domain = self.domain
        self.data_source.save()

        self.report = get_sample_report_config()
        self.report.config_id = self.data_source.get_id
        self.report.domain = self.domain
        self.report.save()

    def tearDown(cls):
        LinkedReportIDMap.objects.all().delete()
        delete_all_report_configs()
        for config in DataSourceConfiguration.all():
            config.delete()
        super().tearDown()

    def test_link_creates_datasource_and_report(self):
        link_info = create_ucr_link(self.domain_link, self.report)

        new_datasource = DataSourceConfiguration.get(link_info.datasource_info.linked_id)
        self.assertEqual(new_datasource.domain, self.domain_link.linked_domain)

        new_report = ReportConfiguration.get(link_info.report_info.linked_id)
        self.assertEqual(new_report.domain, self.domain_link.linked_domain)

    def test_linking_second_report_creates_single_datasource(self):
        create_ucr_link(self.domain_link, self.report)

        new_report = get_sample_report_config()
        new_report.title = "Another Report"
        new_report.config_id = self.data_source.get_id
        new_report.domain = self.domain
        new_report.save()

        create_ucr_link(self.domain_link, new_report)
        self.assertEqual(
            1, LinkedReportIDMap.objects.filter(master_id=self.data_source.get_id).count()
        )
        self.assertEqual(2, len(ReportConfiguration.by_domain(self.domain_link.linked_domain)))
        self.assertItemsEqual(
            [self.report.title, new_report.title],
            [r.title for r in ReportConfiguration.by_domain(self.domain_link.linked_domain)],
        )
