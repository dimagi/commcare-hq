from collections import namedtuple
from django.test import TestCase

from mock import call, patch

from custom.icds.location_reassignment.const import MOVE_OPERATION
from custom.icds.location_reassignment.exceptions import InvalidTransitionError
from custom.icds.location_reassignment.processor import Processor

LocationType = namedtuple("LocationType", ["code"])
Location = namedtuple("Location", ["site_code"])
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
        cls.location_131 = Location(site_code='131')
        cls.location_112 = Location(site_code='112')
        cls.location_13 = Location(site_code='13')
        cls.location_12 = Location(site_code='12')
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

        Processor(self.domain, self.transitions, {}, site_codes).process()
        calls = [call([self.location_112], [self.location_131], MOVE_OPERATION),
                 call([self.location_12], [self.location_13], MOVE_OPERATION)]
        deprecate_locations_mock.assert_has_calls(calls)
        self.assertEqual(deprecate_locations_mock.call_count, 2)

    def test_missing_locations(self, locations_mock, *_):
        locations_mock.return_value = [self.location_131]
        with self.assertRaises(InvalidTransitionError) as e:
            Processor(self.domain, self.transitions, {}, site_codes).process()
            self.assertEqual(str(e.exception), "Could not load location with following site codes: 112")

    @patch('corehq.apps.locations.models.SQLLocation.objects.create')
    def test_creating_new_locations(self, location_create_mock, locations_mock, *_):
        locations_mock.return_value = self.all_locations
        new_location_details = {
            'supervisor': [{
                'name': 'Test 13',
                'site_code': '13',
                'parent_site_code': None,
                'lgd_code': 'LGD 13'
            }]
        }
        Processor(self.domain, self.transitions, new_location_details, site_codes).process()
        location_type_supervisor = None
        for location_type in location_types:
            if location_type.code == 'supervisor':
                location_type_supervisor = location_type
                break
        location_create_mock.assert_called_with(
            domain=self.domain, site_code='13', name='Test 13', parent=None,
            metadata={'lgd_code': 'LGD 13'}, location_type=location_type_supervisor
        )
