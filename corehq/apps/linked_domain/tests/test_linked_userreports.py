import json

from mock import patch

from dimagi.utils.couch.undo import is_deleted, soft_delete

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.linked_domain.applications import link_app
from corehq.apps.linked_domain.decorators import REMOTE_REQUESTER_HEADER
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedAppsTest
from corehq.apps.linked_domain.ucr import create_linked_ucr, update_linked_ucr
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
from corehq.apps.users.models import HQApiKey, WebUser
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

    def tearDown(self):
        delete_all_report_configs()
        for config in DataSourceConfiguration.all():
            config.delete()

        super().tearDown()

    def test_link_creates_datasource_and_report(self):
        link_info = create_linked_ucr(self.domain_link, self.report.get_id)

        new_datasource = DataSourceConfiguration.get(link_info.datasource.get_id)
        self.assertEqual(new_datasource.domain, self.domain_link.linked_domain)

        new_report = ReportConfiguration.get(link_info.report.get_id)
        self.assertEqual(new_report.domain, self.domain_link.linked_domain)
        self.assertEqual(self.report.get_id, new_report.report_meta.master_id)

    def test_linking_second_report_creates_single_datasource(self):
        create_linked_ucr(self.domain_link, self.report.get_id)

        new_report = get_sample_report_config()
        new_report.title = "Another Report"
        new_report.config_id = self.data_source.get_id
        new_report.domain = self.domain
        new_report.save()

        create_linked_ucr(self.domain_link, new_report.get_id)
        self.assertEqual(2, len(ReportConfiguration.by_domain(self.domain_link.linked_domain)))
        self.assertItemsEqual(
            [self.report.title, new_report.title],
            [r.title for r in ReportConfiguration.by_domain(self.domain_link.linked_domain)],
        )

    def test_update_ucr(self):
        linked_report_info = create_linked_ucr(self.domain_link, self.report.get_id)
        self.report.title = "New title"
        self.report.save()

        update_linked_ucr(self.domain_link, linked_report_info.report.get_id)

        report = ReportConfiguration.get(linked_report_info.report.get_id)
        self.assertEqual("New title", report.title)
        self.assertEqual(self.report.get_id, report.report_meta.master_id)
        self.assertNotEqual(self.report.config_id, report.config_id)

    def test_delete_master_deletes_linked(self):
        linked_report_info = create_linked_ucr(self.domain_link, self.report.get_id)
        soft_delete(self.report)
        update_linked_ucr(self.domain_link, linked_report_info.report.get_id)
        report = ReportConfiguration.get(linked_report_info.report.get_id)
        self.assertTrue(is_deleted(report))

        self.report.config.deactivate()
        update_linked_ucr(self.domain_link, linked_report_info.report.get_id)
        report = ReportConfiguration.get(linked_report_info.report.get_id)
        self.assertTrue(report.config.is_deactivated)

    def test_linked_app_filter_maps_correctly(self):
        linked_app = link_app(self.linked_app, self.domain, self.master1.get_id)
        self.data_source.configured_filter = {
            "type": "and",
            "filters": [
                {
                    "type": "boolean_expression",
                    "operator": "eq",
                    "expression": {
                        "type": "property_name",
                        "property_name": "xmlns",
                        "datatype": None
                    },
                    "property_value": "http://openrosa.org/formdesigner/1A255365-DAA1-4815-906D-CBD8D3A462B1",
                    "comment": None
                },
                {
                    "type": "boolean_expression",
                    "operator": "eq",
                    "expression": {
                        "type": "property_name",
                        "property_name": "app_id",
                        "datatype": None
                    },
                    "property_value": self.master1.get_id,
                    "comment": None
                }
            ]
        }
        self.data_source.save()
        linked_report_info = create_linked_ucr(self.domain_link, self.report.get_id)
        self.assertEqual(
            linked_report_info.datasource.configured_filter['filters'][1]['property_value'],
            linked_app.get_id
        )

    @patch('corehq.apps.linked_domain.ucr.remote_get_ucr_config')
    def test_remote_link_ucr(self, fake_ucr_getter):
        create_domain(self.domain)
        self.addCleanup(delete_all_domains)

        couch_user = WebUser.create(self.domain, "test", "foobar")
        django_user = couch_user.get_django_user()
        self.addCleanup(delete_all_users)

        api_key, _ = HQApiKey.objects.get_or_create(user=django_user)
        auth_headers = {'HTTP_AUTHORIZATION': 'apikey test:%s' % api_key.key}
        self.domain_link.save()

        url = reverse('linked_domain:ucr_config', args=[self.domain, self.report.get_id])
        headers = auth_headers.copy()
        headers[REMOTE_REQUESTER_HEADER] = self.domain_link.linked_domain
        resp = self.client.get(url, **headers)

        fake_ucr_getter.return_value = json.loads(resp.content)

        # Create
        linked_report_info = create_linked_ucr(self.domain_link, self.report.get_id)
        self.assertEqual(1, len(ReportConfiguration.by_domain(self.domain_link.linked_domain)))
        self.assertEqual(self.report.get_id, linked_report_info.report.report_meta.master_id)

        # Update
        self.report.title = "Another new title"
        self.report.save()

        update_linked_ucr(self.domain_link, linked_report_info.report.get_id)
        report = ReportConfiguration.get(linked_report_info.report.get_id)
        self.assertEqual("Another new title", report.title)
