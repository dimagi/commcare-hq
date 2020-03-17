import datetime
from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestAdolescent(BaseFormsTest):
    ucr_name = "static-icds-cas-static-adolescent_girls_reg_form"

    def test_with_adolescent_girl_oos(self):
        self._test_data_source_results(
            'adolescent_girls',
            [{
                'admitted_in_school': None,
                "doc_id": None,
                "timeend": datetime.datetime(2019, 12, 9, 8, 23, 52, 511000),
                'out_of_school': 'yes',
                'person_case_id': 'dda684cc-f260-4a0e-b608-f22aca3bf467',
                're_out_of_school': None,
              }
             ])

    def test_with_adolescent_girl_oos_again(self):
        self._test_data_source_results(
            'adolescent_girl_oos_again',
            [{'admitted_in_school': None,
              "doc_id": None,
              "timeend": datetime.datetime(2019, 10, 1, 11, 47, 51, 267000),
              'out_of_school': None,
              'person_case_id': 'b957eacc-03a4-40a4-a4c2-4b1e1e12f931',
              're_out_of_school': 'yes',
              }
             ])

    def test_with_adolescent_girl_school_admit(self):
        self._test_data_source_results(
            'adolescent_girl_school_admit',
            [{'admitted_in_school': 'yes',
              "doc_id": None,
              "timeend": datetime.datetime(2019, 8, 2, 10, 46, 30, 806000),
              'out_of_school': None,
              'person_case_id': '62861fb8-ba76-4505-b90e-b225b8bf02fe',
              're_out_of_school': None,
              }
             ])
