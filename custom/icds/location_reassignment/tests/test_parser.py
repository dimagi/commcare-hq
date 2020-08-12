import tempfile
from collections import namedtuple
from unittest import TestCase

import attr
from mock import patch

from couchexport.export import export_raw
from couchexport.models import Format

from corehq.util.workbook_json.excel import get_workbook
from custom.icds.location_reassignment.const import (
    CURRENT_LGD_CODE,
    CURRENT_NAME,
    CURRENT_PARENT_NAME,
    CURRENT_PARENT_SITE_CODE,
    CURRENT_SITE_CODE_COLUMN,
    NEW_LGD_CODE,
    NEW_NAME,
    NEW_PARENT_SITE_CODE,
    NEW_SITE_CODE_COLUMN,
    NEW_USERNAME_COLUMN,
    OPERATION_COLUMN,
    USERNAME_COLUMN,
)
from custom.icds.location_reassignment.parser import Parser

LocationType = namedtuple("LocationType", ['code', 'parent_type'])
Location = namedtuple("Location", ['location_type', 'site_code'])


class TestParser(TestCase):
    domain = 'test'
    headers = (
        ('awc',
         (CURRENT_NAME, NEW_NAME, CURRENT_SITE_CODE_COLUMN, NEW_SITE_CODE_COLUMN, CURRENT_LGD_CODE,
          NEW_LGD_CODE, CURRENT_PARENT_NAME, CURRENT_PARENT_SITE_CODE, NEW_PARENT_SITE_CODE,
          USERNAME_COLUMN, NEW_USERNAME_COLUMN, OPERATION_COLUMN)),
        ('supervisor',
         (CURRENT_NAME, NEW_NAME, CURRENT_SITE_CODE_COLUMN, NEW_SITE_CODE_COLUMN, CURRENT_LGD_CODE,
          NEW_LGD_CODE, CURRENT_PARENT_NAME, CURRENT_PARENT_SITE_CODE, NEW_PARENT_SITE_CODE,
          USERNAME_COLUMN, NEW_USERNAME_COLUMN, OPERATION_COLUMN)),
        ('state',
         (CURRENT_NAME, NEW_NAME, CURRENT_SITE_CODE_COLUMN, NEW_SITE_CODE_COLUMN, CURRENT_LGD_CODE,
          NEW_LGD_CODE, USERNAME_COLUMN, NEW_USERNAME_COLUMN, OPERATION_COLUMN)),
    )
    rows = (
        ('awc', (
            # invalid Extract operation with no change to site code
            ('AWC 1', 'AWC 1', '111', '111', 'AWC-111',
             'AWC-111', 'Supervisor 1', '11', '11',
             'username1', 'username1', 'Extract'),
            # valid operation to move 112 -> 131
            ('AWC 2', 'AWC 3', 112, 131, 'AWC-112',
             'AWC-131', 'Supervisor 2', '11', 13,
             'username2', 'username3', 'Move'),
            # valid operation to merge 113 114 -> 132 but
            # with different lgd code for new location in 114
            ('AWC 4', 'AWC 6', '113', '132', 'AWC-113',
             'AWC-132', 'Supervisor 1', '11', '13',
             'username4', 'username5', 'Merge'),
            ('AWC 5', 'AWC 6', '114', '132', 'AWC-114',
             'AWC-133', 'Supervisor 1', '11', '13',
             'username6', 'username7', 'Merge'),
            # invalid operation passed with new parent site code
            # of a location getting archived
            ('AWC 7', 'AWC 8', '115', '133', 'AWC-115',
             'AWC-133', 'Supervisor 2', '11', '12',
             'username6', 'username7', 'Move'),
            ('AWC 7', '  ', '116', '134', 'AWC-116',
             'AWC-134', 'Supervisor 2', '11', '13',
             'username6', 'username7', 'Move'),
        )),
        ('supervisor', (
            # invalid row with missing new site code
            ('Supervisor 1', 'Supervisor 1', '11', '', 'Sup-11',
             'Sup-11', 'State 1', '1', '1',
             'username4', 'username4', 'Split'),
            # valid operation to move 12 -> 13
            ('Supervisor 2', 'Supervisor 3', '12', '13', 'Sup-12',
             'Sup-13', 'State 1', '1', '1',
             'username5', 'username6', 'Move'),
            # invalid values for site codes
            ('Supervisor 4', 'Supervisor 5', 'Invalid $ite #code', 'NEW-- $ite #code', 'Sup-12',
             'Sup-14', 'State 1', '1', '?--123--?',
             'username7', 'username8', 'Move'),
        )),
        ('state', (
            # invalid row with unknown operation
            ('State 1', 'State 1', '1', '1', 'State-1',
             'State-11', 'username4', 'username4', 'Unknown'),
            ('State 2', 'State 3', '2', '3', '',
             '', '', '', 'Move'),
        ))
    )

    @classmethod
    def setUpClass(cls):
        cls.state_location_type = LocationType(code='state', parent_type=None)
        cls.supervisor_location_type = LocationType(code='supervisor', parent_type=cls.state_location_type)
        cls.awc_location_type = LocationType(code='awc', parent_type=cls.supervisor_location_type)
        cls.location_types = [cls.state_location_type, cls.supervisor_location_type, cls.awc_location_type]

    @patch('custom.icds.location_reassignment.parser.Parser.validate')
    @patch('corehq.apps.locations.models.LocationType.objects')
    def test_parser(self, location_type_mock, _):
        location_type_mock.by_domain.return_value = self.location_types
        location_type_mock.select_related.return_value.filter.return_value = self.location_types
        with tempfile.TemporaryFile() as file:
            export_raw(self.headers, self.rows, file, format=Format.XLS_2007)
            file.seek(0)
            workbook = get_workbook(file)
            parser = Parser(self.domain, workbook)
            errors = parser.parse()
            self.assertEqual(len(parser.valid_transitions['awc']), 2)
            awc_transitions = [attr.asdict(t) for t in parser.valid_transitions['awc']]
            self.assertEqual(
                awc_transitions,
                [
                    {
                        'domain': self.domain,
                        'location_type_code': 'awc',
                        'operation': 'Move',
                        'old_site_codes': ['112'],
                        'new_site_codes': ['131'],
                        'new_location_details': {
                            '131': {'name': 'AWC 3 [131]', 'parent_site_code': '13', 'lgd_code': 'AWC-131',
                                    'sub_district_name': None}},
                        'user_transitions': {'username2': 'username3'}
                    },
                    {
                        'domain': self.domain,
                        'location_type_code': 'awc',
                        'operation': 'Move',
                        'old_site_codes': ['115'],
                        'new_site_codes': ['133'],
                        'new_location_details': {
                            '133': {'name': 'AWC 8 [133]', 'parent_site_code': '12', 'lgd_code': 'AWC-133',
                                    'sub_district_name': None}},
                        'user_transitions': {'username6': 'username7'}
                    }

                ]
            )
            self.assertEqual(len(parser.valid_transitions['supervisor']), 1)
            supervisor_transition = attr.asdict(parser.valid_transitions['supervisor'][0])
            self.assertEqual(
                supervisor_transition,
                {'domain': self.domain,
                 'location_type_code': 'supervisor',
                 'operation': 'Move',
                 'old_site_codes': ['12'],
                 'new_site_codes': ['13'],
                 'new_location_details': {
                     '13': {
                         'name': 'Supervisor 3 [13]',
                         'parent_site_code': '1',
                         'lgd_code': 'Sup-13',
                         'sub_district_name': None
                     }
                 },
                 'user_transitions': {'username5': 'username6'}}
            )
            self.assertEqual(len(parser.valid_transitions['state']), 1)
            state_transition = attr.asdict(parser.valid_transitions['state'][0])
            self.assertEqual(
                state_transition,
                {'domain': self.domain,
                 'location_type_code': 'state',
                 'operation': 'Move',
                 'old_site_codes': ['2'],
                 'new_site_codes': ['3'],
                 'new_location_details': {
                     '3': {
                         'name': 'State 3',
                         'parent_site_code': '',
                         'lgd_code': '',
                         'sub_district_name': None
                     }
                 },
                 'user_transitions': {}}
            )
            self.assertEqual(errors, [
                "Invalid Operation Unknown",
                "Missing location code for operation Split. Got old: '11' and new: ''",
                "Got invalid location code 'invalid $ite #code' for operation Move",
                "Got invalid location code 'new-- $ite #code' for operation Move",
                "Got invalid parent location code '?--123--?' for new location "
                "'new-- $ite #code' for operation Move",
                "No change in location code for operation Extract. Got old: '111' and new: '111'",
                "New location 132 passed with different information",
                "Missing new location name for 134"
            ])

    @patch('custom.icds.location_reassignment.parser.Parser._validate_usernames')
    @patch('custom.icds.location_reassignment.parser.Parser._validate_new_site_codes_type')
    @patch('custom.icds.location_reassignment.parser.Parser._validate_descendants_deprecated')
    @patch('custom.icds.location_reassignment.parser.Parser._validate_old_locations')
    @patch('corehq.apps.locations.models.SQLLocation.active_objects')
    @patch('corehq.apps.locations.models.LocationType.objects')
    def test_validate_parents(self, location_type_mock, locations_mock, *_):
        location_type_mock.by_domain.return_value = self.location_types
        location_type_mock.select_related.return_value.filter.return_value = self.location_types
        locations_mock.select_related.return_value.filter.return_value = [
            Location(site_code='13', location_type=self.state_location_type)
        ]
        with tempfile.TemporaryFile() as file:
            export_raw(self.headers, self.rows, file, format=Format.XLS_2007)
            file.seek(0)
            workbook = get_workbook(file)
            parser = Parser(self.domain, workbook)
            errors = parser.parse()
            self.assertIn('Unexpected non-state parent 1 set for supervisor', errors, "missing location found")
            self.assertIn('Unexpected state parent 13 set for awc', errors, "incorrect parent type not flagged")
            self.assertIn('Parent 12 is marked for archival', errors, "archived parent not caught")

    @patch('custom.icds.location_reassignment.parser.Parser._validate_usernames')
    @patch('custom.icds.location_reassignment.parser.Parser._validate_parents')
    @patch('custom.icds.location_reassignment.parser.Parser._validate_descendants_deprecated')
    @patch('custom.icds.location_reassignment.parser.Parser._validate_old_locations')
    @patch('corehq.apps.locations.models.SQLLocation.active_objects')
    @patch('corehq.apps.locations.models.LocationType.objects')
    def test_validate_new_site_codes_type(self, location_type_mock, locations_mock, *_):
        location_type_mock.by_domain.return_value = self.location_types
        location_type_mock.select_related.return_value.filter.return_value = self.location_types
        locations_mock.select_related.return_value.filter.return_value = [
            Location(site_code='13', location_type=self.state_location_type)
        ]
        with tempfile.TemporaryFile() as file:
            export_raw(self.headers, self.rows, file, format=Format.XLS_2007)
            file.seek(0)
            workbook = get_workbook(file)
            parser = Parser(self.domain, workbook)
            errors = parser.parse()
            self.assertIn('state 13 used as supervisor', errors)
            self.assertIn('state 13 used as awc', errors)
            self.assertNotIn('state 13 used as state', errors)
