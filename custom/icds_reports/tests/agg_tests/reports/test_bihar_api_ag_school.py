
from django.test import TestCase
from custom.icds_reports.reports.bihar_api import get_api_ag_school_data
from datetime import date
from custom.icds_reports.models.aggregate import BiharAPIDemographics
from mock import patch


@patch('custom.icds_reports.utils.aggregation_helpers.distributed.bihar_api_demographics.BiharApiDemographicsHelper.bihar_state_id',
       'st1')
class SchoolAPITest(TestCase):

    def test_file_content(self):
        BiharAPIDemographics.aggregate(date(2017, 5, 1))
        data, count = get_api_ag_school_data(
            month=date(2017, 5, 1).strftime("%Y-%m-%d"),
            state_id='st1',
            last_person_case_id=''
        )
        expected_count = 10
        expected_result = {"person_id": "85585a4c-469e-4cfc-b261-f5ff6f4bdff1", "person_name": None,
                           "out_of_school_status": 3, "last_class_attended_ever": 5, 'was_oos_ever': 1}
        for item in data:
            if item['person_id'] == "85585a4c-469e-4cfc-b261-f5ff6f4bdff1":
                first_person_case = item
                break
        self.assertDictEqual(expected_result, first_person_case)
        self.assertEqual(expected_count, count)
