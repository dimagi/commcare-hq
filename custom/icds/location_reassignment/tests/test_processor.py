from collections import namedtuple
from unittest import TestCase

from mock import call, patch

from custom.icds.location_reassignment.const import MOVE_OPERATION
from custom.icds.location_reassignment.processor import Processor

LocationType = namedtuple("LocationType", ["code"])
Location = namedtuple("Location", ["site_code"])


class TestProcessor(TestCase):
    domain = "test"

    @patch('custom.icds.location_reassignment.processor.deprecate_locations')
    @patch('corehq.apps.locations.models.SQLLocation.active_objects.filter')
    @patch('corehq.apps.locations.models.LocationType.objects.by_domain')
    def test_process(self, location_types_mock, locations_mock, deprecate_locations_mock):
        type_codes = ['state', 'supervisor', 'awc']
        site_codes = ['131', '112', '13', '12']
        location_types_mock.return_value = list(map(lambda site_code: LocationType(code=site_code), type_codes))
        location_131 = Location(site_code='131')
        location_112 = Location(site_code='112')
        location_13 = Location(site_code='13')
        location_12 = Location(site_code='12')
        locations = [location_12, location_13, location_112, location_131]
        locations_mock.return_value = locations
        transitions = {
            'awc': {
                'Move': {'131': '112'},
            },
            'supervisor': {
                'Move': {'13': '12'}
            },
            'state': {}
        }
        Processor(self.domain, transitions, site_codes).process()
        calls = [call(MOVE_OPERATION, [location_131], [location_112]),
                 call(MOVE_OPERATION, [location_13], [location_12])]
        deprecate_locations_mock.assert_has_calls(calls)
        self.assertEqual(deprecate_locations_mock.call_count, 2)
