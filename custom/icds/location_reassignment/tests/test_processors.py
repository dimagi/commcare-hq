from collections import namedtuple
from unittest import TestCase as UnitTestTestCase

from django.test import TestCase

from mock import call, patch

from custom.icds.location_reassignment.const import MOVE_OPERATION
from custom.icds.location_reassignment.processor import (
    HouseholdReassignmentProcessor,
    Processor,
)

LocationType = namedtuple("LocationType", ["code"])
Location = namedtuple("Location", ["location_id", "site_code"])
type_codes = ['state', 'supervisor', 'awc']
location_types = list(map(lambda site_code: LocationType(code=site_code), type_codes))


@patch('corehq.apps.locations.models.LocationType.objects.by_domain', return_value=location_types)
class TestProcessor(TestCase):
    domain = "test"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.transitions = {
            'awc': [
                {
                    'domain': cls.domain,
                    'location_type_code': 'awc',
                    'operation': MOVE_OPERATION,
                    'old_site_codes': ['112'],
                    'new_site_codes': ['131'],
                    'new_location_details': {
                        '131': {
                            'name': 'Test 131',
                            'parent_site_code': '13',
                            'lgd_code': 'LGD 131'
                        }
                    },
                    'user_transitions': {'username_new': 'username_old'}
                }
            ],
            'supervisor': [
                {
                    'domain': cls.domain,
                    'location_type_code': 'supervisor',
                    'operation': MOVE_OPERATION,
                    'old_site_codes': ['12'],
                    'new_site_codes': ['13'],
                    'new_location_details': {
                        '13': {
                            'name': 'Test 13',
                            'parent_site_code': None,
                            'lgd_code': 'LGD 13'
                        }
                    }}
            ],
            'state': []
        }

    @patch('custom.icds.location_reassignment.processor.Transition')
    def test_process(self, transition_mock, *mocks):
        Processor(self.domain, self.transitions).process()
        calls = [call(**self.transitions['supervisor'][0]),
                 call().perform(),
                 call(**self.transitions['awc'][0]),
                 call().perform()]
        transition_mock.assert_has_calls(calls)


class TestHouseholdReassignmentProcessor(UnitTestTestCase):
    domain = "test"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.location_1 = Location(location_id='199', site_code='1')
        cls.location_2 = Location(location_id='299', site_code='2')
        cls.location_3 = Location(location_id='399', site_code='3')
        cls.location_4 = Location(location_id='499', site_code='4')
        cls.all_locations = [cls.location_1, cls.location_2, cls.location_3, cls.location_4]
        cls.reassignments = {
            'household_case_id1': {'old_site_code': '1', 'new_site_code': '2'},
            'household_case_id2': {'old_site_code': '3', 'new_site_code': '4'},
        }

    @patch('custom.icds.location_reassignment.utils.reassign_household')
    @patch('custom.icds.location_reassignment.processor.get_supervisor_id')
    @patch('custom.icds.location_reassignment.processor.SQLLocation.active_objects.filter')
    @patch('custom.icds.location_reassignment.processor.SQLLocation.objects.filter')
    def test_process(self, old_locations_fetch_mock, new_locations_fetch_mock, supervisor_id_mock,
                     reassign_household_mock):
        old_locations_fetch_mock.return_value = [self.location_1, self.location_3]
        new_locations_fetch_mock.return_value = [self.location_2, self.location_4]
        supervisor_id_mock.return_value = 'a_supervisor_id'
        HouseholdReassignmentProcessor(self.domain, self.reassignments).process()
        old_locations_fetch_mock.assert_called_once_with(domain=self.domain, site_code__in={'1', '3'})
        new_locations_fetch_mock.assert_called_once_with(domain=self.domain, site_code__in={'2', '4'})
        supervisor_id_mock.assert_has_calls([
            call(self.domain, '199'),
            call(self.domain, '399')
        ])
        reassign_household_mock.assert_has_calls([
            call(self.domain, 'household_case_id1', '199', '299', 'a_supervisor_id'),
            call(self.domain, 'household_case_id2', '399', '499', 'a_supervisor_id')
        ])
