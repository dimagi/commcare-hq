from __future__ import absolute_import
from __future__ import unicode_literals

import json
import mock

from datetime import date
from io import open

from django.test import TestCase

from corehq.util.files import TransientTempfile
from custom.icds_reports.reports.disha import DishaDump


class DishaFileBuildTest(TestCase):

    @mock.patch('custom.icds_reports.reports.disha.DishaDump._get_rows')
    def test_file_content(self, disha_get_rows_mock):
        class CountableList(list):
            # this will be mocked for a Queryset object which needs count method
            def count(self, *args, **kwargs):
                return len(self)

        data = [['a'], ['b'], ["d\xc3\xa9f"]]
        disha_get_rows_mock.return_value = CountableList(data)

        month = date(2018, 8, 1)
        state = 'Andhra pradesh'
        with TransientTempfile() as temp_path:
            dump = DishaDump(state, month)
            with open(temp_path, 'w+b') as f:
                dump._write_data(f)
            with open(temp_path, 'r', encoding='utf-8') as f:
                expected_json = {
                    'month': str(month),
                    'state_name': state,
                    'column_names': dump._get_columns(),
                    'rows': data
                }
                self.assertEqual(json.loads(f.read()), expected_json)
