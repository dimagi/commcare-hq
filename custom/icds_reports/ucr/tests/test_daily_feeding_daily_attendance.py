from mock import patch

from custom.icds_reports.ucr.tests.test_base_form_ucr import BaseFormsTest
from decimal import Decimal
from django.test import override_settings


@patch('custom.icds_reports.ucr.expressions._get_user_location_id',
       lambda user_id: 'qwe56poiuytr4xcvbnmkjfghwerffdaa')
@patch('corehq.apps.locations.ucr_expressions._get_location_type_name',
       lambda loc_id, context: 'awc')
@patch('custom.icds_reports.ucr.expressions.GetAppVersion.get_version_from_app_object',
       lambda self, item, app_version: 20000)
class TestDailyFeedingForms(BaseFormsTest):
    ucr_name = "static-icds-cas-static-daily_feeding_forms"

    @override_settings(SERVER_ENVIRONMENT='icds-cas')
    def test_daily_feeding_form_when_fetching_app_version_from_string(self):
        self._test_data_source_results(
            'daily_feeding_attendence', [
                {
                    'attendance_full': 0,
                    'attendance_non': 1,
                    'attendance_partial': 0,
                    'attended_children': 1,
                    'attended_children_percent': Decimal('0.333333333333333314829616256247390992939472198486328125'),
                    'awc_not_open': 0,
                    'awc_not_open_department_work': 0,
                    'awc_not_open_festival': 0,
                    'awc_not_open_holiday': 0,
                    'awc_not_open_no_help': 0,
                    'awc_not_open_other': 0,
                    'awc_open_count': 1,
                    'count': 1,
                    'days_thr_provided_count': 0,
                    'doc_id': None,
                    'eligible_children': 3,
                    'form_location': '30.7265 76.8422026 314.1 22.15',
                    'form_location_lat': Decimal('30.7265'),
                    'form_location_long': Decimal('76.8422026'),
                    'image_name': '1580901745211.jpg',
                    'month': None,
                    'open_bfast_count': 1,
                    'open_four_acts_count': 0,
                    'open_hotcooked_count': 1,
                    'open_one_acts_count': 0,
                    'open_pse_count': 1,
                    'pse_conducted': 0,
                    'submitted_on': None
                }])

    @override_settings(SERVER_ENVIRONMENT='india')
    def test_daily_feeding_form_when_fetching_app_version_from_app(self):
        self._test_data_source_results(
            'daily_feeding_attendence', [
                {
                    'attendance_full': 0,
                    'attendance_non': 0,
                    'attendance_partial': 1,
                    'attended_children': 2,
                    'attended_children_percent': Decimal('0.66666666666666662965923251249478198587894439697265625'),
                    'awc_not_open': 0,
                    'awc_not_open_department_work': 0,
                    'awc_not_open_festival': 0,
                    'awc_not_open_holiday': 0,
                    'awc_not_open_no_help': 0,
                    'awc_not_open_other': 0,
                    'awc_open_count': 1,
                    'count': 1,
                    'days_thr_provided_count': 0,
                    'doc_id': None,
                    'eligible_children': 3,
                    'form_location': '30.7265 76.8422026 314.1 22.15',
                    'form_location_lat': Decimal('30.7265'),
                    'form_location_long': Decimal('76.8422026'),
                    'image_name': '1580901745211.jpg',
                    'month': None,
                    'open_bfast_count': 1,
                    'open_four_acts_count': 0,
                    'open_hotcooked_count': 1,
                    'open_one_acts_count': 0,
                    'open_pse_count': 1,
                    'pse_conducted': 0,
                    'submitted_on': None
                }])
