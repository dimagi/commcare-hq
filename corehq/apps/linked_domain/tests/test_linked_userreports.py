import json

from mock import patch
from tastypie.models import ApiKey

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.linked_domain.decorators import REMOTE_REQUESTER_HEADER
from corehq.apps.linked_domain.models import LinkedReportIDMap
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.ucr import create_ucr_link
from corehq.apps.userreports.dbaccessors import delete_all_report_configs
from corehq.apps.userreports.models import (
    DataSourceConfiguration,
    ReportConfiguration,
)
from corehq.apps.userreports.tests.utils import (
    get_sample_data_source,
    get_sample_report_config,
)
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import WebUser
from corehq.util import reverse


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

        delete_all_users()
        delete_all_domains()
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

    @patch('corehq.apps.linked_domain.ucr.remote_get_ucr_config')
    def test_remote_link_ucr(self, fake_ucr_getter):
        create_domain(self.domain)
        couch_user = WebUser.create(self.domain, "test", "foobar")
        django_user = couch_user.get_django_user()
        api_key, _ = ApiKey.objects.get_or_create(user=django_user)
        auth_headers = {'HTTP_AUTHORIZATION': 'apikey test:%s' % api_key.key}
        self.domain_link.save()

        url = reverse('linked_domain:ucr_config', args=[self.domain, self.report.get_id])
        headers = auth_headers.copy()
        headers[REMOTE_REQUESTER_HEADER] = self.domain_link.linked_domain
        resp = self.client.get(url, **headers)

        fake_ucr_getter.return_value = json.loads(resp.content)

        create_ucr_link(self.domain_link, self.report)
        self.assertEqual(1, len(ReportConfiguration.by_domain(self.domain_link.linked_domain)))
