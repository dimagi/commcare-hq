from __future__ import absolute_import
from __future__ import unicode_literals

import datetime
from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


class TestLsVhndForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-ls_vhnd_form"

    @patch('custom.icds_reports.ucr.expressions._get_user_location_id', lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
    def test_vhnd_form_with_vhnd_date(self):
        self._test_data_source_results(
            'ls_vhnd_observation_form',
          [
            {'submitted_on': None,
             'doc_id': None,
             'location_id': 'qwe56poiuytr4xcvbnmkjfghwerffdaa',
             'vhnd_date': datetime.date(2018, 8, 24),
             'month': None}
          ])
