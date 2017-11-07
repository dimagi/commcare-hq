from __future__ import absolute_import
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
from lxml import etree

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
        days_open.return_value = etree.fromstring(self.get_xml('days_open_fixture'))
        weighed.return_value = etree.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = etree.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = etree.fromstring(self.get_xml('visit_fixture'))
        indicator = LSAggregatePerformanceIndicator('domain', 'user')
        message = indicator.get_messages(language_code='en')[0]
        self.assertIn('Home visits completed on time / Home visits completed: 22 / 269', message)
        self.assertIn('Beneficiaries received adequate THR / Beneficiaries eligible for THR: 19 / 34', message)
        self.assertIn('Children weighed under 3 years / Total children under 3 years: 30 / 33', message)
        self.assertIn('Average days AWC open / Goal: 59 / 25', message)


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
        days_open.return_value = etree.fromstring(self.get_xml('days_open_fixture'))
        weighed.return_value = etree.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = etree.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = etree.fromstring(self.get_xml('visit_fixture'))
        indicator = AWWAggregatePerformanceIndicator(self.domain, self.aww)
        message = indicator.get_messages(language_code='en')[0]
        self.assertIn('Home visits completed / Goal: 6 / 65', message)
        self.assertIn('Beneficiaries received adequate THR / Beneficiaries eligible for THR: 1 / 2', message)
        self.assertIn('Children weighed under 3 years / Total children under 3 years: 1 / 2', message)
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
        indicator = AWWAggregatePerformanceIndicator(self.domain, aww3)
        with self.assertRaises(Exception) as e:
            indicator.get_messages(language_code='en')
        self.assertIn('AWC AWC3 not found in the restore', e.exception.message)

    @patch.object(LSAggregatePerformanceIndicator, 'visits_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'thr_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'weighed_fixture', new_callable=PropertyMock)
    @patch.object(LSAggregatePerformanceIndicator, 'days_open_fixture', new_callable=PropertyMock)
    def test_attribute_not_in_fixtures(self, days_open, weighed, thr, visits):
        days_open.return_value = etree.fromstring(self.get_xml('bad_days_open_fixture'))
        weighed.return_value = etree.fromstring(self.get_xml('weighed_fixture'))
        thr.return_value = etree.fromstring(self.get_xml('thr_fixture'))
        visits.return_value = etree.fromstring(self.get_xml('visit_fixture'))
        indicator = AWWAggregatePerformanceIndicator(self.domain, self.aww)
        with self.assertRaises(Exception) as e:
            indicator.get_messages(language_code='en')
        self.assertIn('Attribute awc_opened_count not found in restore for AWC AWC1', e.exception.message)
