from mock import patch
import datetime
from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
class TestPrivateSchoolUcr(BaseFormsTest):
    ucr_name = "static-icds-cas-static-dashboard_primary_private_school"

    def test_private_school_question(self):
        self._test_data_source_results(
            'private_school', [{
                'admitted_private_school': 'yes',
                'date_admission_private_school': datetime.date(2019, 11, 21),
                'admitted_primary_school': None,
                'date_admission_primary_school': None,
                'person_case_id': '8076f5f1-f77c-444b-a956-e5dd1d01b678',
                'date_return_private_school': None,
                'returned_private_school': None,
                'timeend': datetime.datetime(2019, 11, 21, 6, 47, 12, 148000),
                'doc_id': None
            }
            ])

    def test_private_school_question_return(self):
        self._test_data_source_results(
            'private_school_returned_case', [{
                'admitted_private_school': None,
                'date_admission_private_school': None,
                'admitted_primary_school': None,
                'date_admission_primary_school': None,
                'person_case_id': 'df2aa0ce-f6f8-4850-a0af-2be87b0717ca',
                'date_return_private_school': datetime.date(2019, 10, 18),
                'returned_private_school': 'yes',
                'timeend': datetime.datetime(2019, 10, 18, 11, 20, 10, 718000),
                'doc_id': None
            }
            ])
