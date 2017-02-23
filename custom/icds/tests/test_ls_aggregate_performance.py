import xml.etree.ElementTree as ET

from django.test import SimpleTestCase, TestCase
from mock import patch, Mock

from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.tests.util import (
    LocationStructure,
    LocationTypeStructure,
    setup_location_types_with_structure,
    setup_locations_with_structure,
)
from corehq.apps.users.models import CommCareUser

from custom.icds.messaging.indicators import (
    LSAggregatePerformanceIndicator,
    AWWAggregatePerformanceIndicator,
)


class PropertyMock(Mock):
    def __get__(self, instance, owner):
        return self()


class TestLSAggregatePerformanceIndicator(SimpleTestCase, TestXmlMixin):
    file_path = ('../../../..', 'custom/icds/tests/data/fixtures')

    @patch.object(LSAggregatePerformanceIndicator, 'visits_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'thr_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'weighed_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'days_open_fixture', new_callable=PropertyMock)
    def test_report_parsing(self, days_open, weighed, thr, visits):
        days_open.return_value = ET.fromstring(self.get_xml('days_open_fixture'))
        weighed.return_value = ET.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = ET.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = ET.fromstring(self.get_xml('visit_fixture'))
        indicator = LSAggregatePerformanceIndicator('domain', 'user')
        message = indicator.get_messages()[0]
        self.assertTrue('Timely Home Visits - 22 / 269' in message)
        self.assertTrue('Received adequate THR / Due for THR - 19 / 34' in message)
        self.assertTrue('Number of children weighed - 30 / 33' in message)
        self.assertTrue('Days AWC open - 59' in message)


class TestAWWAggregatePerformanceIndicator(TestCase, TestXmlMixin):
    domain = 'domain'
    file_path = ('../../../..', 'custom/icds/tests/data/fixtures')

    @classmethod
    def setUpClass(cls):
        super(TestAWWAggregatePerformanceIndicator, cls).setUpClass()
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
        cls.aww.delete()
        cls.ls.delete()
        for l in cls.locs.values():
            l.delete()
        for l in cls.loc_types.values():
            l.delete()
        cls.domain_obj.delete()
        super(TestAWWAggregatePerformanceIndicator, cls).tearDownClass()

    @classmethod
    def _make_user(cls, name, location):
        user = CommCareUser.create(cls.domain, name, 'password')
        user.set_location(location)
        return user

    @patch.object(LSAggregatePerformanceIndicator, 'visits_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'thr_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'weighed_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'days_open_fixture', new_callable=PropertyMock)
    def test_report_parsing(self, days_open, weighed, thr, visits):
        days_open.return_value = ET.fromstring(self.get_xml('days_open_fixture'))
        weighed.return_value = ET.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = ET.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = ET.fromstring(self.get_xml('visit_fixture'))
        indicator = AWWAggregatePerformanceIndicator(self.domain, self.aww)
        message = indicator.get_messages()[0]
        self.assertTrue('Home Visits - 6 / 65' in message)
        self.assertTrue('Received adequate THR / Due for THR - 1 / 2' in message)
        self.assertTrue('Number of children weighed - 1 / 2' in message)
        self.assertTrue('Days AWC open - 3' in message)

    @patch.object(LSAggregatePerformanceIndicator, 'visits_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'thr_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'weighed_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'days_open_fixture', new_callable=PropertyMock)
    def test_user_not_in_fixtures(self, days_open, weighed, thr, visits):
        aww3 = self._make_user('aww3', self.locs['AWC3'])
        self.addCleanup(aww3.delete)
        days_open.return_value = ET.fromstring(self.get_xml('days_open_fixture'))
        weighed.return_value = ET.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = ET.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = ET.fromstring(self.get_xml('visit_fixture'))
        indicator = AWWAggregatePerformanceIndicator(self.domain, aww3)
        with self.assertRaises(Exception) as e:
            indicator.get_messages()
        self.assertIn('AWC AWC3 not found in the restore', e.exception.message)

    @patch.object(LSAggregatePerformanceIndicator, 'visits_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'thr_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'weighed_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'days_open_fixture', new_callable=PropertyMock)
    def test_attribute_not_in_fixtures(self, days_open, weighed, thr, visits):
        days_open.return_value = ET.fromstring(self.get_xml('bad_days_open_fixture'))
        weighed.return_value = ET.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = ET.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = ET.fromstring(self.get_xml('visit_fixture'))
        indicator = AWWAggregatePerformanceIndicator(self.domain, self.aww)
        with self.assertRaises(Exception) as e:
            indicator.get_messages()
        self.assertIn('Attribute awc_opened_count not found in restore for AWC AWC1', e.exception.message)
