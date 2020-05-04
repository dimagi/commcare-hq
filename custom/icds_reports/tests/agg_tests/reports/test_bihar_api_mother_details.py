import datetime
from django.test import TestCase
from custom.icds_reports.reports.bihar_api import get_mother_details
from custom.icds_reports.tasks import  update_bihar_api_table
from datetime import date

from mock import patch


@patch('custom.icds_reports.utils.aggregation_helpers.distributed.bihar_api_demographics.BiharApiDemographicsHelper.bihar_state_id',
       'st1')
class BiharAPIMotherTest(TestCase):

    def test_file_content(self):
        update_bihar_api_table(date(2017, 5, 1))
        data, count = get_mother_details(
            month=date(2017, 5, 1).strftime("%Y-%m-%d"),
            state_id='st1',
            last_ccs_case_id=''
        )

        for case in data:
            if case['ccs_case_id'] == '08d215e7-81c7-4ad3-9c7d-1b27f0ed4bb5':
                ccs_case_details = case
                break

        self.assertEqual(
            {
                "household_id": 'b6a55583-e07d-4367-ae5c-f3ff22f85271',
                "person_id": "cc75916b-a71e-4c4d-a537-5c7bef95b12f",
                "ccs_case_id": "08d215e7-81c7-4ad3-9c7d-1b27f0ed4bb5",
                "married": 1,
                "husband_name": "test_husband_name",
                "husband_id": "b1e7f7d8-149e-4ffc-a876-2a70a469edbc",
                "last_preg_year": 12,
                "is_pregnant": 1,
                "preg_reg_date": datetime.date(2017, 4, 12),
                "tt_1": datetime.date(2017, 5, 1),
                'tt_2': datetime.date(2017, 5, 2),
                "tt_booster": datetime.date(2017, 5, 3),
                "hb": 2,
                "add": datetime.date(2017, 6, 1),
                "last_preg_tt": None,
                "lmp": datetime.date(2016, 10, 2)
             },
            ccs_case_details
        )
