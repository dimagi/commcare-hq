
from django.test import TestCase
from custom.icds_reports.reports.bihar_api import get_api_demographics_data
from datetime import date
from custom.icds_reports.models.aggregate import BiharAPIDemographics, AwcLocation
from mock import patch


@patch('custom.icds_reports.utils.aggregation_helpers.distributed.bihar_api_demographics.BiharApiDemographicsHelper.bihar_state_id',
       'st1')
class DemographicsAPITest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(DemographicsAPITest, cls).setUpClass()
        BiharAPIDemographics.aggregate(date(2017, 5, 1))

    def test_file_content(self):

        data = get_api_demographics_data(
            month=date(2017, 5, 1),
            state_id='st1',
            last_person_case_id=''
        )
        first_person_case = data['data'][0]
        self.assertCountEqual(
            {"state_name": "Bihar", "state_site_code": "st1",
             "district_name": "d1", "district_site_code": "d1",
             "block_name": "b2", "block_site_code": "b2",
             "supervisor_name": "s4", "supervisor_site_code": "s4",
             "awc_name": "a36", "awc_site_code": "a36",
             "ward_number": "", "household_id": '0c05ae24-3d23-4382-a346-8d053c1ec81c',
             "household_name": None, "hh_reg_date": None,
             "hh_num": None, "hh_gps_location": None,
             "hh_caste": None, "hh_bpl_apl": None,
             "hh_minority": None, "hh_religion": None,
             "hh_member_number": None,
             "person_id": "008b146c-0f21-4506-8800-6cdf5f0d04fc",
             "person_name": None, "has_adhaar": 0,
             "bank_account_number": '123456789', "ifsc_code": 'testcode1234',
             "age_at_reg": 28, "dob": "1988-04-07", "gender": "F",
             "blood_group": 'APos', "disabled": None,
             "disability_type": None, "referral_status": 'reffered',
             "migration_status": None, "resident": 1,
             "registered_status": None, "rch_id": 1234,
             "mcts_id": 213, "phone_number": None,
             "date_death": None, "site_death": None,
             "closed_on": None, "reason_closure": None},
            first_person_case
        )
