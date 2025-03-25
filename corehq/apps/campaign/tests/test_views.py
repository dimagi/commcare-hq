import uuid
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from corehq.apps.campaign.models import (
    Dashboard,
    DashboardMap,
    DashboardReport,
    DashboardTab,
    WidgetType,
)
from corehq.apps.campaign.views import (
    DashboardView,
    DashboardWidgetView,
    PaginatedCasesWithGPSView,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.geospatial.const import GPS_POINT_CASE_PROPERTY
from corehq.apps.users.models import WebUser
from corehq.form_processor.tests.utils import create_case
from corehq.util.test_utils import flag_enabled


class BaseTestCampaignView(TestCase):
    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.username = 'test-user'
        cls.password = 'safe-password'
        cls.webuser = WebUser.create(
            cls.domain,
            cls.username,
            cls.password,
            created_by=None,
            created_via=None,
            is_admin=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.webuser.delete(None, None)
        cls.domain_obj.delete()
        super().tearDownClass()

    @property
    def endpoint(self):
        return reverse(self.urlname, args=[self.domain])

    @property
    def login_endpoint(self):
        return reverse('domain_login', kwargs={'domain': self.domain})

    def _make_request(self, query_data={}, headers=None, is_logged_in=True):
        if is_logged_in:
            self.client.login(username=self.username, password=self.password)
        return self.client.get(self.endpoint, query_data, headers=headers)


class TestDashboardView(BaseTestCampaignView):
    urlname = DashboardView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dashboard = Dashboard.objects.create(domain=cls.domain)
        cls.dashboard_map_cases = DashboardMap.objects.create(
            dashboard=cls.dashboard,
            title='Cases Map',
            case_type='foo',
            geo_case_property='somewhere',
            dashboard_tab=DashboardTab.CASES,
        )
        cls.dashboard_map_mobile_workers = DashboardMap.objects.create(
            dashboard=cls.dashboard,
            title='Mobile Workers Map',
            description='My cool map',
            case_type='bar',
            geo_case_property='nowhere',
            dashboard_tab=DashboardTab.MOBILE_WORKERS,
        )

    def test_not_logged_in(self):
        response = self._make_request(is_logged_in=False)
        self.assertRedirects(response, f"{self.login_endpoint}?next={self.endpoint}")

    def test_ff_not_enabled(self):
        response = self._make_request(is_logged_in=True)
        assert response.status_code == 404

    @flag_enabled('CAMPAIGN_DASHBOARD')
    def test_success(self):
        response = self._make_request(is_logged_in=True)
        assert response.status_code == 200

        context = response.context
        assert context['map_widgets'] == {
            'cases': [{
                'id': self.dashboard_map_cases.id,
                'title': 'Cases Map',
                'description': None,
                'case_type': 'foo',
                'geo_case_property': 'somewhere',
            }],
            'mobile_workers': [{
                'id': self.dashboard_map_mobile_workers.id,
                'title': 'Mobile Workers Map',
                'description': 'My cool map',
                'case_type': 'bar',
                'geo_case_property': 'nowhere',
            }],
        }


@es_test(requires=[case_search_adapter], setup_class=True)
class TestPaginatedCasesWithGPSView(BaseTestCampaignView):
    case_type = 'person'
    gps_property = 'location'
    urlname = PaginatedCasesWithGPSView.urlname

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.case_a = create_case(
            cls.domain,
            case_id=uuid4().hex,
            case_type=cls.case_type,
            name='CaseA',
            case_json={
                cls.gps_property: '12.34 45.67'
            },
            save=True,
        )
        cls.case_b = create_case(
            cls.domain,
            case_id=uuid4().hex,
            case_type=cls.case_type,
            name='CaseB',
            case_json={
                cls.gps_property: '23.45 56.78'
            },
            save=True,
        )
        case_search_adapter.bulk_index([cls.case_a, cls.case_b], refresh=True)

    def test_not_logged_in(self):
        response = self._make_request(is_logged_in=False)
        self.assertRedirects(response, f"{self.login_endpoint}?next={self.endpoint}")

    def test_get_paginated_cases_with_gps(self):
        query_data = {
            'case_type': self.case_type,
            'gps_prop_name': self.gps_property,
        }
        response = self._make_request(query_data)
        assert response.status_code == 200

        json_data = response.json()
        assert json_data['total'] == 2


class TestDashboardWidgetView(BaseTestCampaignView):
    urlname = DashboardWidgetView.urlname

    def tearDown(self):
        DashboardMap.objects.all().delete()
        DashboardReport.objects.all().delete()
        super().tearDown()

    def test_not_logged_in(self):
        response = self._make_request(is_logged_in=False)
        self.assertRedirects(response, f"{self.login_endpoint}?next={self.endpoint}")

    def test_ff_not_enabled(self):
        response = self._make_request(is_logged_in=True)
        assert response.status_code == 404

    @flag_enabled('CAMPAIGN_DASHBOARD')
    @patch('corehq.apps.campaign.forms.DashboardMapForm._get_case_types', return_value=[])
    def test_new_map_widget(self, *args):
        response = self._make_request(
            query_data={'widget_type': WidgetType.MAP},
            headers={'hq-hx-action': 'new_widget'},
            is_logged_in=True,
        )

        self._assert_for_success(response, WidgetType.MAP)

    @flag_enabled('CAMPAIGN_DASHBOARD')
    @patch('corehq.apps.campaign.forms.DashboardReportForm._get_report_configurations', return_value=[])
    def test_new_report_widget(self, *args):
        response = self._make_request(
            query_data={'widget_type': WidgetType.REPORT},
            headers={'hq-hx-action': 'new_widget'},
            is_logged_in=True,
        )

        self._assert_for_success(response, WidgetType.REPORT)

    @flag_enabled('CAMPAIGN_DASHBOARD')
    def test_new_widget_invalid_widget_type(self, *args):
        response = self._make_request(
            query_data={'widget_type': 'invalid'},
            headers={'hq-hx-action': 'new_widget'},
            is_logged_in=True,
        )
        assert response.context['htmx_error'].message == "Requested widget type is not supported"

    @flag_enabled('CAMPAIGN_DASHBOARD')
    @patch('corehq.apps.campaign.forms.DashboardMapForm._get_case_types')
    def test_save_map_widget(self, mocked_case_types):
        mocked_case_types.return_value = [('case-02', 'case-02')]

        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.endpoint,
            data={
                "title": "Map Widget",
                "description": "Sample widget",
                "dashboard_tab": DashboardTab.CASES,
                "case_type": "case-02",
                "geo_case_property": "Test",
                "submit": "Submit",
                "widget_type": WidgetType.MAP
            },
            headers={'hq-hx-action': 'save_widget'},
        )

        self._assert_for_success(response, WidgetType.MAP)
        assert DashboardMap.objects.count() == 1

    @flag_enabled('CAMPAIGN_DASHBOARD')
    @patch('corehq.apps.campaign.forms.DashboardReportForm._get_report_configurations')
    def test_save_report_widget(self, mocked_get_report_configurations):
        report_id = uuid.uuid4().hex
        mocked_get_report_configurations.return_value = [(report_id, 'Test Report')]

        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.endpoint,
            data={
                "title": "New Report Widget",
                "description": "Sample widget",
                "dashboard_tab": DashboardTab.MOBILE_WORKERS,
                "report_configuration_id": report_id,
                "widget_type": WidgetType.REPORT
            },
            headers={'hq-hx-action': 'save_widget'},
        )

        self._assert_for_success(response, WidgetType.REPORT)
        assert DashboardReport.objects.count() == 1

    @flag_enabled('CAMPAIGN_DASHBOARD')
    def test_save_widget_form_error(self):
        self.client.login(username=self.username, password=self.password)
        response = self.client.post(
            self.endpoint,
            data={
                "title": "New Report Widget",
                "description": "Sample widget",
                "dashboard_tab": DashboardTab.CASES,
                "widget_type": WidgetType.REPORT
            },
            headers={'hq-hx-action': 'save_widget'},
        )

        self._assert_for_success(response, WidgetType.REPORT)
        assert DashboardReport.objects.count() == 0
        assert response.context["widget_form"].errors == {'report_configuration_id': ['This field is required.']}

    @staticmethod
    def _assert_for_success(response, widget_type):
        assert response.status_code == 200
        assert response.context['widget_type'] == widget_type
        assert isinstance(response.context['widget_form'], WidgetType.get_form_class(widget_type))


class TestGetGeoCaseProperties(BaseTestCampaignView):
    urlname = 'get_geo_case_properties'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_not_logged_in(self):
        response = self._make_request(is_logged_in=False)
        self.assertRedirects(response, f"{self.login_endpoint}?next={self.endpoint}")

    @patch('corehq.apps.campaign.views.get_gps_properties', return_value={'geo_prop'})
    def test_success(self, *args):
        response = self._make_request(is_logged_in=True, query_data={'case_type': 'case1'})
        assert response.status_code == 200
        assert response.context['geo_case_props'] == ['geo_prop', GPS_POINT_CASE_PROPERTY]

    def test_missing_case_type(self, *args):
        response = self._make_request(is_logged_in=True)
        assert response.status_code == 400
        assert response.content == b'case_type param is required'
