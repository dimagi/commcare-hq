from unittest import TestCase

from mock import patch

from corehq.util.workbook_json.excel import get_workbook
from custom.icds.location_reassignment.dumper import Dumper


class TestDumper(TestCase):
    domain = "test"

    @patch('custom.icds.location_reassignment.dumper.Dumper._old_location_ids_by_site_code')
    @patch('corehq.form_processor.interfaces.dbaccessors.CaseAccessors.get_case_ids_by_owners')
    @patch('corehq.apps.locations.models.SQLLocation.inactive_objects.filter')
    @patch('corehq.apps.locations.models.SQLLocation.active_objects.filter')
    def test_dump(self, mock_active_site_codes_search, mock_inactive_site_codes_search, mock_case_count,
                  mock_location_ids):
        mock_case_count.return_value = []
        transitions = {
            'awc': {
                'Move': {'112': '111'},  # new: old
                'Merge': {'115': ['113', '114']},  # new: old
                'Split': {'116': ['117', '118']},  # old: new
                'Extract': {'120': '119'}  # new: old
            },
            'supervisor': {
                'Move': {'13': '12'}
            },
            'state': {}
        }

        mock_location_ids.return_value = {
            '111': 'locationid111',
            '113': 'locationid113',
            '114': 'locationid114',
            '116': 'locationid116',
            '119': 'locationid119',
            '12': 'locationid12'
        }
        mock_active_site_codes_search.return_value.values_list.return_value = ['112', '115', '117']
        mock_inactive_site_codes_search.return_value.values_list.return_value = ['120']
        filestream = Dumper(self.domain).dump(transitions)
        workbook = get_workbook(filestream)
        awc_worksheet_rows = list(workbook.get_worksheet('awc'))
        supervisor_worksheet_rows = list(workbook.get_worksheet('supervisor'))
        self.assertEqual(
            supervisor_worksheet_rows,
            [
                {'from': '12', 'transition': 'Move', 'to': '13',
                 'Missing': True, 'Archived': False, 'Cases': 0}
            ]
        )
        self.assertEqual(
            awc_worksheet_rows,
            [
                {'from': '111', 'transition': 'Move', 'to': '112',
                 'Missing': False, 'Archived': False, 'Cases': 0},
                {'from': '113', 'transition': 'Merge', 'to': '115',
                 'Missing': False, 'Archived': False, 'Cases': 0},
                {'from': '114', 'transition': 'Merge', 'to': '115',
                 'Missing': False, 'Archived': False, 'Cases': 0},
                {'from': '116', 'transition': 'Split', 'to': '117',
                 'Missing': False, 'Archived': False, 'Cases': 0},
                {'from': '116', 'transition': 'Split', 'to': '118',
                 'Missing': True, 'Archived': False, 'Cases': 0},
                {'from': '119', 'transition': 'Extract', 'to': '120',
                 'Missing': True, 'Archived': True, 'Cases': 0}
            ]
        )
