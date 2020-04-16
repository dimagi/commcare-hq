import datetime
from django.test import TestCase
from custom.icds_reports.reports.bihar_api import get_mother_details
from datetime import date
from custom.icds_reports.models.aggregate import BiharAPIMotherDetails
from mock import patch


@patch('custom.icds_reports.utils.aggregation_helpers.distributed.bihar_api_mother_details.BiharApiMotherDetailsHelper.bihar_state_id',
       'st1')
class DemographicsAPITest(TestCase):

    def test_file_content(self):
        BiharAPIMotherDetails.aggregate(date(2017, 5, 1))
        data, count = get_mother_details(
            month=date(2017, 5, 1).strftime("%Y-%m-%d"),
            state_id='st1',
            last_ccs_case_id=''
        )
        ccs_case_details = data[23]
        self.assertCountEqual(
            {
                "household_id": 'b6a55583-e07d-4367-ae5c-f3ff22f85271',
                "person_id": "cc75916b-a71e-4c4d-a537-5c7bef95b12f",
                "ccs_case_id": "08d215e7-81c7-4ad3-9c7d-1b27f0ed4bb5",
                "married": 1,
                "husband_name": "test_husband_name",
                "husband_id": "fcbafe96-f73d-4930-9277-b42965b8419d",
                "last_preg_year": 12,
                "is_pregnant": 1,
                "preg_reg_date": datetime.date(2017, 4, 12),
                "tt_1": None,
                "tt_2": None,
                "tt_booster": datetime.date(2017, 5, 3),
                "hb": 2,
                "add": datetime.date(2017, 6, 1),
             },
            ccs_case_details
        )
