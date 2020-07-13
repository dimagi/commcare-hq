from mock import patch
import datetime
from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest
from decimal import Decimal
from django.test import override_settings


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
@patch('custom.icds_reports.ucr.expressions.GetAppVersion.get_version_from_app_object',
       lambda self, item, app_version: 20000)
class TestUsageForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-usage_forms"

    @override_settings(SERVER_ENVIRONMENT='icds-cas')
    def test_usage_form_when_fetching_app_version_from_string(self):
        self._test_data_source_results(
            'daily_feeding_attendence', [
                {
                    'add_household': 0,
                    'add_person': 0,
                    'add_pregnancy': 0,
                    'app_version': 3,
                    'bp_time': None,
                    'bp_tri1': 0,
                    'bp_tri2': 0,
                    'bp_tri3': 0,
                    'cf': 0,
                    'cf_time': None,
                    'commcare_version': '2.47.5',
                    'delivery': 0,
                    'delivery_time': None,
                    'doc_id': None,
                    'due_list_ccs': 0,
                    'due_list_child': 0,
                    'ebf': 0,
                    'ebf_time': None,
                    'form_date': None,
                    'form_time': datetime.datetime(2020, 2, 5, 11, 22, 29, 539000),
                    'gmp': 0,
                    'gmp_time': None,
                    'home_visit': 0,
                    'home_visit_time_of_day': None,
                    'month': None,
                    'pnc': 0,
                    'pnc_time': None,
                    'pse': 1,
                    'pse_time': Decimal('69.13700000000000045474735088646411895751953125'),
                    'pse_time_of_day': datetime.datetime(2020, 2, 5, 11, 22, 29, 539000),
                    'thr': 0,
                    'thr_time': None
                }])
