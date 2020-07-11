import datetime
from unittest import skip

from django.test import TestCase
from custom.icds_reports.reports.bihar_api import get_api_vaccine_data
from datetime import date
from mock import patch

from custom.icds_reports.tasks import update_child_vaccine_table


class VaccinesAPITest(TestCase):

    @skip("""dependency bug: local variable 'first_person_case' referenced before assignment

    This fails with Django 2.2 on Travis. It also fails in the same way
    when running this test by itself on Django 1.11 on master:
    ./manage.py test custom.icds_reports.tests.agg_tests.reports.test_bihar_api_vaccines
    """)
    def test_file_content(self):
        update_child_vaccine_table(date(2017, 5, 1))
        data, count = get_api_vaccine_data(
            month=date(2017, 5, 1).strftime("%Y-%m-%d"),
            state_id='st1',
            last_person_case_id=''
        )
        for item in data:
            if item['person_id'] == 'fb0f06e3-4d36-42bb-a260-70520af83ce4':
                first_person_case = item
                break
        self.assertDictEqual(
            {'month': datetime.date(2017, 5, 1), 'person_id': 'fb0f06e3-4d36-42bb-a260-70520af83ce4',
             'time_birth': None, 'child_alive': None, 'father_name': None, 'mother_name': None, 'father_id': None,
             'mother_id': None, 'dob': datetime.date(2003, 2, 19), 'private_admit': None, 'primary_admit': None,
             'date_last_private_admit': None, 'date_return_private': None, 'due_list_date_1g_dpt_1': None,
             'due_list_date_2g_dpt_2': datetime.date(2017, 3, 1), 'due_list_date_3g_dpt_3': None,
             'due_list_date_5g_dpt_booster': None, 'due_list_date_7gdpt_booster_2': None,
             'due_list_date_0g_hep_b_0': None, 'due_list_date_1g_hep_b_1': None, 'due_list_date_2g_hep_b_2': None,
             'due_list_date_3g_hep_b_3': None, 'due_list_date_3g_ipv': None, 'due_list_date_4g_je_1': None,
             'due_list_date_5g_je_2': None, 'due_list_date_5g_measles_booster': None, 'due_list_date_4g_measles': None,
             'due_list_date_0g_opv_0': None, 'due_list_date_1g_opv_1': None, 'due_list_date_2g_opv_2': None,
             'due_list_date_3g_opv_3': None, 'due_list_date_5g_opv_booster': None, 'due_list_date_1g_penta_1': None,
             'due_list_date_2g_penta_2': None, 'due_list_date_3g_penta_3': None, 'due_list_date_1g_rv_1': None,
             'due_list_date_2g_rv_2': None, 'due_list_date_3g_rv_3': None, 'due_list_date_4g_vit_a_1': None,
             'due_list_date_5g_vit_a_2': None, 'due_list_date_6g_vit_a_3': None, 'due_list_date_6g_vit_a_4': None,
             'due_list_date_6g_vit_a_5': None, 'due_list_date_6g_vit_a_6': None, 'due_list_date_6g_vit_a_7': None,
             'due_list_date_6g_vit_a_8': None, 'due_list_date_7g_vit_a_9': None, 'birth_weight': None,
             'due_list_date_1g_bcg': datetime.date(2017, 3, 1), 'delivery_nature': 'vaginal', 'term_days': 311,
             'last_reported_fever_date': None}
            ,
            first_person_case
        )
        self.assertEqual(48, count)
