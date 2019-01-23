from __future__ import absolute_import
from __future__ import unicode_literals

import datetime

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest

class TestcbeForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-cbe_form"

    def test_cbe_form_date(self):
        self._test_data_source_results(
            'cbe_form', [{
                'submitted_on': None,
                'doc_id': None,
                'date_cbe_organise': datetime.date(2018, 12, 10)
            }
            ])
