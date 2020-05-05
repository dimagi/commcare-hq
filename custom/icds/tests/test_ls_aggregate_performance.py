import uuid

from django.test import TestCase

from casexml.apps.phone.tests.utils import create_restore_user

import mock
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.tests.util import (
    LocationStructure,
    LocationTypeStructure,
    setup_location_types_with_structure,
    setup_locations_with_structure,
)
from corehq.apps.userreports.tests.utils import get_sample_report_config
from corehq.apps.users.models import CommCareUser
from corehq.util.test_utils import flag_enabled
from custom.icds.messaging.custom_content import run_indicator_for_user
from custom.icds.messaging.indicators import (
    AWWAggregatePerformanceIndicator,
    IndicatorError,
    LSAggregatePerformanceIndicator,
    _get_report_fixture_for_user,
)
from lxml import etree
from mock import Mock, patch


class PropertyMock(Mock):
    def __get__(self, instance, owner):
        return self()


class BaseAggregatePerformanceTestCase(TestCase, TestXmlMixin):
    domain = 'domain'
    file_path = ('../../../..', 'custom/icds/tests/data/fixtures')

    @classmethod
    def setUpClass(cls):
        super(BaseAggregatePerformanceTestCase, cls).setUpClass()
        cls.domain_obj = create_domain(cls.domain)

        location_type_structure = [
            LocationTypeStructure('supervisor', [
                LocationTypeStructure('awc', [])
            ])
        ]
        location_structure = [
            LocationStructure('LSL', 'supervisor', [
                LocationStructure('AWC1', 'awc', []),
                LocationStructure('AWC2', 'awc', []),
                LocationStructure('AWC3', 'awc', []),
            ])
        ]
        cls.loc_types = setup_location_types_with_structure(cls.domain, location_type_structure)
        cls.locs = setup_locations_with_structure(cls.domain, location_structure)
        cls.ls = cls._make_user('ls', cls.locs['LSL'])
        cls.aww = cls._make_user('aww', cls.locs['AWC1'])

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(BaseAggregatePerformanceTestCase, cls).tearDownClass()

    @classmethod
    def _make_user(cls, name, location):
        user = CommCareUser.create(cls.domain, name, 'password')
        user.set_location(location)
        return user


class TestLSAggregatePerformanceIndicator(BaseAggregatePerformanceTestCase):

    @patch.object(LSAggregatePerformanceIndicator, 'visits_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'thr_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'weighed_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'days_open_fixture', new_callable=PropertyMock)
    def test_report_parsing(self, days_open, weighed, thr, visits):
        days_open.return_value = etree.fromstring(self.get_xml('days_open_fixture'))
        weighed.return_value = etree.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = etree.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = etree.fromstring(self.get_xml('visit_fixture'))
        [message] = run_indicator_for_user(self.ls, LSAggregatePerformanceIndicator, language_code='en')
        self.assertIn('Number of visits / Number of desired visits: 45 / 195', message)
        self.assertIn('Number of visits on time / Number of visits: 16 / 45', message)
        self.assertIn('THR Distribution: 19 / 34', message)
        self.assertIn('Number of children weighed: 30 / 33', message)
        self.assertIn('Average no. of days AWC open / Goal: 3 / 25', message)


class TestAWWAggregatePerformanceIndicator(BaseAggregatePerformanceTestCase):

    @patch.object(LSAggregatePerformanceIndicator, 'visits_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'thr_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'weighed_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'days_open_fixture', new_callable=PropertyMock)
    def test_report_parsing(self, days_open, weighed, thr, visits):
        days_open.return_value = etree.fromstring(self.get_xml('days_open_fixture'))
        weighed.return_value = etree.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = etree.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = etree.fromstring(self.get_xml('visit_fixture'))
        [message] = run_indicator_for_user(self.aww, AWWAggregatePerformanceIndicator, language_code='en')
        self.assertIn('Number of visits / Number of desired visits: 6 / 65', message)
        self.assertIn('Number of visits on time / Number of visits: 2 / 6', message)
        self.assertIn('THR Distribution: 1 / 2', message)
        self.assertIn('Number of children weighed: 1 / 2', message)
        self.assertIn('Days AWC open / Goal: 3 / 25', message)

    @patch.object(LSAggregatePerformanceIndicator, 'visits_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'thr_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'weighed_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'days_open_fixture', new_callable=PropertyMock)
    def test_user_not_in_fixtures(self, days_open, weighed, thr, visits):
        aww3 = self._make_user('aww3', self.locs['AWC3'])
        self.addCleanup(aww3.delete)
        days_open.return_value = etree.fromstring(self.get_xml('days_open_fixture'))
        weighed.return_value = etree.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = etree.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = etree.fromstring(self.get_xml('visit_fixture'))
        [message] = run_indicator_for_user(aww3, AWWAggregatePerformanceIndicator, language_code='en')
        self.assertIn('Number of visits / Number of desired visits: 0 / 65', message)
        self.assertIn('Number of visits on time / Number of visits: 0 / 0', message)
        self.assertIn('THR Distribution: 0 / 0', message)
        self.assertIn('Number of children weighed: 0 / 0', message)
        self.assertIn('Days AWC open / Goal: 0 / 25', message)

    @patch.object(LSAggregatePerformanceIndicator, 'visits_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'thr_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'weighed_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'days_open_fixture', new_callable=PropertyMock)
    def test_attribute_not_in_fixtures(self, days_open, weighed, thr, visits):
        days_open.return_value = etree.fromstring(self.get_xml('bad_days_open_fixture'))
        weighed.return_value = etree.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = etree.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = etree.fromstring(self.get_xml('visit_fixture'))
        with self.assertRaises(IndicatorError) as e:
            run_indicator_for_user(self.aww, AWWAggregatePerformanceIndicator, language_code='en')
        self.assertIn('Attribute awc_opened_count not found in restore for AWC AWC1', str(e.exception))


@flag_enabled('MOBILE_UCR')
class TestGetReportFixture(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestGetReportFixture, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.domain_obj = create_domain(cls.domain)
        cls.user = create_restore_user(cls.domain)

        cls.report_config1 = get_sample_report_config()
        cls.report_config1.domain = cls.domain
        cls.report_config1.save()

    @classmethod
    def tearDownClass(cls):
        cls.report_config1.delete()
        cls.domain_obj.delete()
        super(TestGetReportFixture, cls).tearDownClass()

    def test_get_report_fixture_for_user(self):
        from corehq.apps.userreports.reports.data_source import ConfigurableReportDataSource
        from corehq.apps.userreports.tests.utils import mock_datasource_config
        from corehq.apps.app_manager.models import ReportAppConfig

        app_report_config = ReportAppConfig.wrap({
            'report_id': self.report_config1.get_id,
            'uuid': 'abcdef'
        })
        with mock.patch.object(ConfigurableReportDataSource, 'get_data') as get_data_mock, \
            mock.patch('custom.icds.messaging.indicators.get_report_configs') as get_report_configs:
            get_report_configs.return_value = {'test_id': app_report_config}
            get_data_mock.return_value = [{'owner': 'bob', 'count': 3, 'is_starred': True}]

            with mock_datasource_config():
                fixture = _get_report_fixture_for_user(self.domain, 'test_id', self.user).decode('utf8')
                self.assertIn(self.report_config1.get_id, fixture)
