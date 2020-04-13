from collections import namedtuple
from unittest import TestCase as UnitTestTestCase

from django.test import TestCase

from mock import call, patch

from custom.icds.location_reassignment.const import MOVE_OPERATION
from custom.icds.location_reassignment.exceptions import InvalidTransitionError
from custom.icds.location_reassignment.processor import (
    HouseholdReassignmentProcessor,
    Processor,
)

LocationType = namedtuple("LocationType", ["code"])
Location = namedtuple("Location", ["location_id", "site_code"])
type_codes = ['state', 'supervisor', 'awc']
location_types = list(map(lambda site_code: LocationType(code=site_code), type_codes))
site_codes = ['131', '112', '13', '12']


@patch('corehq.apps.locations.models.LocationType.objects.by_domain', return_value=location_types)
@patch('custom.icds.location_reassignment.processor.deprecate_locations', return_value=[])
@patch('corehq.apps.locations.models.SQLLocation.active_objects.filter')
class TestProcessor(TestCase):
    domain = "test"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.location_131 = Location(location_id='13199', site_code='131')
        cls.location_112 = Location(location_id='11299', site_code='112')
        cls.location_13 = Location(location_id='1399', site_code='13')
        cls.location_12 = Location(location_id='1299', site_code='12')
        cls.all_locations = [cls.location_12, cls.location_13, cls.location_112, cls.location_131]
        cls.transitions = {
            'awc': {
                'Move': {'131': '112'},
            },
            'supervisor': {
                'Move': {'13': '12'}
            },
            'state': {}
        }

    def test_process(self, locations_mock, deprecate_locations_mock, *_):
        locations_mock.return_value = self.all_locations

        Processor(self.domain, self.transitions, {}, {}, site_codes).process()
        calls = [call(self.domain, [self.location_112], [self.location_131], MOVE_OPERATION),
                 call(self.domain, [self.location_12], [self.location_13], MOVE_OPERATION)]
        deprecate_locations_mock.assert_has_calls(calls)
        self.assertEqual(deprecate_locations_mock.call_count, 2)

    def test_missing_locations(self, locations_mock, *_):
        locations_mock.return_value = [self.location_131]
        with self.assertRaises(InvalidTransitionError) as e:
            Processor(self.domain, self.transitions, {}, {}, site_codes).process()
            self.assertEqual(str(e.exception), "Could not load location with following site codes: 112")

    @patch('corehq.apps.locations.models.SQLLocation.objects.create')
    def test_creating_new_locations(self, location_create_mock, locations_mock, *_):
        locations_mock.return_value = self.all_locations
        location_create_mock.return_value = "A New Location"
        new_location_details = {
            'supervisor': {
                '13': {
                    'name': 'Test 13',
                    'parent_site_code': None,
                    'lgd_code': 'LGD 13'
                }
            },
            'awc': {
                '131': {
                    'name': 'Test 131',
                    'parent_site_code': '13',
                    'lgd_code': 'LGD 131'
                }

            }
        }
        Processor(self.domain, self.transitions, new_location_details, {}, site_codes).process()
        location_type_supervisor = None
        location_type_awc = None
        for location_type in location_types:
            if location_type.code == 'supervisor':
                location_type_supervisor = location_type
            elif location_type.code == 'awc':
                location_type_awc = location_type
        calls = [
            call(domain=self.domain, site_code='13', name='Test 13', parent=None,
                 metadata={'lgd_code': 'LGD 13'}, location_type=location_type_supervisor),
            call(domain=self.domain, site_code='131', name='Test 131', parent="A New Location",
                 metadata={'lgd_code': 'LGD 131'}, location_type=location_type_awc)
        ]
        location_create_mock.assert_has_calls(calls)

    @patch('custom.icds.location_reassignment.tasks.update_usercase.delay')
    def test_updating_cases(self, update_usercase_mock, locations_mock, *_):
        locations_mock.return_value = self.all_locations
        user_transitions = {
            'username_new': 'username_old'
        }
        Processor(self.domain, self.transitions, {}, user_transitions, site_codes).process()
        update_usercase_mock.assert_called_with(
            self.domain, 'username_new', 'username_old'
        )


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

    @patch('custom.icds.location_reassignment.utils.reassign_household_case')
    @patch('custom.icds.location_reassignment.processor.get_supervisor_id')
    @patch('custom.icds.location_reassignment.processor.SQLLocation.active_objects.filter')
    def test_process(self, locations_fetch_mock, supervisor_id_mock, reassign_household_mock):
        locations_fetch_mock.return_value = self.all_locations
        supervisor_id_mock.return_value = 'a_supervisor_id'
        HouseholdReassignmentProcessor(self.domain, self.reassignments).process()
        locations_fetch_mock.assert_has_calls([
            call(domain=self.domain, site_code__in={'1', '3'}),
            call(domain=self.domain, site_code__in={'2', '4'})
        ])
        supervisor_id_mock.assert_has_calls([
            call(self.domain, '199'),
            call(self.domain, '399')
        ])
        reassign_household_mock.assert_has_calls([
            call(self.domain, 'household_case_id1', '199', '299', 'a_supervisor_id'),
            call(self.domain, 'household_case_id2', '399', '499', 'a_supervisor_id')
        ])
