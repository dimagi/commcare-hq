from datetime import date

from custom.icds_reports.models.aggregate import ChildVaccines
from django.test.testcases import TestCase

from custom.icds_reports.tasks import update_child_vaccine_table

class ChildVaccineAggregationTest(TestCase):
    always_include_columns = {'due_list_date_anc_1', 'due_list_date_anc_2', 'due_list_date_anc_3',
                              'due_list_date_anc_4', 'due_list_date_tt_1', 'due_list_date_tt_2',
                              'due_list_date_tt_booster', 'due_list_date_1g_bcg'}

    def test_child_agg_2017_05_01(self):
        update_child_vaccine_table(date(2017, 5, 1))
        actual_data = ChildVaccines.objects.filter(child_health_case_id='0a04f052-f32b-4874-b38b-d21244f81516').\
            values(*self.always_include_columns)
        self.assertEqual(actual_data[0],
                         {'due_list_date_anc_1': '2017-03-01', 'due_list_date_anc_2': '2017-03-01',
                          'due_list_date_anc_3': '2017-03-01', 'due_list_date_anc_4': '2017-03-01',
                          'due_list_date_tt_1': '2017-03-01', 'due_list_date_tt_2': '2017-03-01',
                          'due_list_date_tt_booster': '2017-03-01', 'due_list_date_1g_bcg': '2017-03-01'
                          }
                         )
