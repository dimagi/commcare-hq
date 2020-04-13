import tempfile
from collections import namedtuple
from unittest import TestCase

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

LocationType = namedtuple("LocationType", ['code'])


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
            ('AWC 2', 'AWC 3', '112', '131', 'AWC-112',
             'AWC-131', 'Supervisor 2', '11', '13',
             'username2', 'username3', 'Move'),
            # valid operation to merge 113 114 -> 132 but
            # with different lgd code for new location in 114
            ('AWC 4', 'AWC 6', '113', '132', 'AWC-113',
             'AWC-132', 'Supervisor 1', '11', '13',
             'username4', 'username5', 'Merge'),
            ('AWC 5', 'AWC 6', '114', '132', 'AWC-114',
             'AWC-133', 'Supervisor 1', '11', '13',
             'username6', 'username7', 'Merge'))),
        ('supervisor', (
            # invalid row with missing new site code
            ('Supervisor 1', 'Supervisor 1', '11', '', 'Sup-11',
             'Sup-11', 'State 1', '1', '1',
             'username4', 'username4', 'Split'),
            # valid operation to move 12 -> 13
            ('Supervisor 2', 'Supervisor 3', '12', '13', 'Sup-12',
             'Sup-13', 'State 1', '1', '1',
             'username5', 'username6', 'Move'))),
        ('state', (
            # invalid row with unknown operation
            ('State 1', 'State 1', '1', '1', 'State-1',
             'State-11', 'username4', 'username4', 'Unknown')))
    )

    @patch('custom.icds.location_reassignment.parser.Parser.validate')
    @patch('corehq.apps.locations.models.LocationType.objects.by_domain')
    def test_parser(self, location_type_mock, _):
        type_codes = ['state', 'supervisor', 'awc']
        location_type_mock.return_value = list(map(lambda site_code: LocationType(code=site_code), type_codes))
        with tempfile.TemporaryFile() as file:
            export_raw(self.headers, self.rows, file, format=Format.XLS_2007)
            file.seek(0)
            workbook = get_workbook(file)
            valid_transitions, errors = Parser(self.domain, workbook).parse()
            self.assertEqual(valid_transitions['awc']['Move'], {'131': '112'})
            self.assertEqual(valid_transitions['awc']['Merge'], {'132': ['113', '114']})
            self.assertEqual(valid_transitions['supervisor']['Move'], {'13': '12'})
            self.assertEqual(errors, [
                "No change in location code for Extract, got old: '111' and new: '111'",
                "New location 132 reused with different information",
                "Missing location code for Split, got old: '11' and new: ''",
                "Invalid Operation Unknown"
            ])
