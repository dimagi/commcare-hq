from __future__ import absolute_import
from __future__ import unicode_literals

from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestTHRFormsV2(BaseFormsTest):
    ucr_name = "static-icds-cas-static-thr_forms_v2"

    def test_with_image_taken(self):
        self._test_data_source_results(
            'thr_form_v2',
            [{'count': 1,
                "doc_id": None,
                "submitted_on": None,
                'photo_thr_packets_distributed': u'1558605103125.jpg',
              }
             ])

    def test_without_image_taken(self):
        self._test_data_source_results(
            'thr_form_v2_without_image',
            [{'count': 1,
                "doc_id": None,
                "submitted_on": None,
                'photo_thr_packets_distributed': ''
              }])
