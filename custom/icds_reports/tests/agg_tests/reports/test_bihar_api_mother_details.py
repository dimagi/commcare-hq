import datetime
from datetime import date

from django.test import TestCase
from mock import patch

from custom.icds_reports.reports.bihar_api import get_mother_details
from custom.icds_reports.tasks import update_bihar_api_table


@patch(
    'custom.icds_reports.utils.aggregation_helpers.distributed.bihar_api_demographics.BiharApiDemographicsHelper.bihar_state_id',
    'st1')
class BiharAPIMotherTest(TestCase):

    def test_pregnant_mother_current_month_positive_ifa(self):
        update_bihar_api_table(date(2017, 5, 1))
        data, count = get_mother_details(
            month=date(2017, 5, 1).strftime("%Y-%m-%d"),
            state_id='st1',
            last_ccs_case_id=''
        )

        for case in data:
            if case['ccs_case_id'] == 'c7c368d4-e554-4e12-a62f-87403453a515':
                ccs_case_details = case
                break

        self.assertEqual(
            {
                'add': datetime.date(2017, 6, 1),
                'anc_1': None,
                'anc_2': None,
                'anc_3': None,
                'anc_4': None,
                'causes_for_ifa': None,
                'ccs_case_id': 'c7c368d4-e554-4e12-a62f-87403453a515',
                'edd': datetime.date(2017, 8, 31),
                'hb': None,
                'household_id': None,
                'husband_id': None,
                'husband_name': None,
                'ifa_consumed_7_days': 4,
                'is_pregnant': 1,
                'last_preg_tt': None,
                'last_preg_year': None,
                'lmp': datetime.date(2016, 11, 24),
                'married': None,
                'maternal_complications': None,
                'person_id': '3c9658d5-e522-4f2c-b636-3ed194d89cb1',
                'preg_reg_date': datetime.date(2017, 4, 12),
                'total_ifa_tablets_received': 10,
                'tt_1': None,
                'tt_2': None,
                'tt_booster': None
            },
            ccs_case_details
        )

    def test_pregnant_mother_current_month_negative_ifa(self):
        update_bihar_api_table(date(2017, 5, 1))
        data, count = get_mother_details(
            month=date(2017, 5, 1).strftime("%Y-%m-%d"),
            state_id='st1',
            last_ccs_case_id=''
        )

        for case in data:
            if case['ccs_case_id'] == 'f3d9aeb7-d3f5-49d1-aa78-4f33aa5cee77':
                ccs_case_details = case
                break

        self.assertEqual(
            {
                'add': datetime.date(2017, 6, 1),
                'anc_1': None,
                'anc_2': None,
                'anc_3': None,
                'anc_4': None,
                'causes_for_ifa': None,
                'ccs_case_id': 'f3d9aeb7-d3f5-49d1-aa78-4f33aa5cee77',
                'edd': datetime.date(2017, 7, 9),
                'hb': None,
                'household_id': None,
                'husband_id': None,
                'husband_name': None,
                'ifa_consumed_7_days': 4,
                'is_pregnant': 1,
                'last_preg_tt': None,
                'last_preg_year': None,
                'lmp': datetime.date(2016, 10, 2),
                'married': None,
                'maternal_complications': None,
                'person_id': 'e94393fd-5007-48f3-95fb-fc1c7f6d3bce',
                'preg_reg_date': datetime.date(2017, 4, 12),
                'total_ifa_tablets_received': -10,
                'tt_1': None,
                'tt_2': None,
                'tt_booster': None
            },
            ccs_case_details
        )

    def test_non_pregnant_mother_current_month_negative_ifa(self):
        update_bihar_api_table(date(2017, 5, 1))
        data, count = get_mother_details(
            month=date(2017, 5, 1).strftime("%Y-%m-%d"),
            state_id='st1',
            last_ccs_case_id=''
        )

        for case in data:
            if case['ccs_case_id'] == '10a53900-f65e-46b7-ae0c-f32a208c0677':
                ccs_case_details = case
                break

        self.assertEqual(
            {
                'add': datetime.date(2017, 3, 20),
                'anc_1': None,
                'anc_2': None,
                'anc_3': None,
                'anc_4': None,
                'causes_for_ifa': None,
                'ccs_case_id': '10a53900-f65e-46b7-ae0c-f32a208c0677',
                'edd': datetime.date(2017, 8, 8),
                'hb': None,
                'household_id': None,
                'husband_id': None,
                'husband_name': None,
                'ifa_consumed_7_days': 2,
                'is_pregnant': None,
                'last_preg_tt': None,
                'last_preg_year': None,
                'lmp': datetime.date(2016, 11, 1),
                'married': None,
                'maternal_complications': None,
                'person_id': '177bdbb3-d4db-4077-9720-86a99b12ba25',
                'preg_reg_date': None,
                'total_ifa_tablets_received': -90,
                'tt_1': None,
                'tt_2': None,
                'tt_booster': None
            },
            ccs_case_details
        )

    def test_pregnant_mother_past_month_negative_ifa(self):
        update_bihar_api_table(date(2017, 5, 1))
        data, count = get_mother_details(
            month=date(2017, 5, 1).strftime("%Y-%m-%d"),
            state_id='st1',
            last_ccs_case_id=''
        )

        for case in data:
            if case['ccs_case_id'] == '9bd35459-6a3c-43ad-a144-0c0013b4272e':
                ccs_case_details = case
                break

        self.assertEqual(
            {
                'add': datetime.date(2017, 6, 1),
                'anc_1': None,
                'anc_2': None,
                'anc_3': None,
                'anc_4': None,
                'causes_for_ifa': None,
                'ccs_case_id': '9bd35459-6a3c-43ad-a144-0c0013b4272e',
                'edd': datetime.date(2017, 8, 31),
                'hb': 2,
                'household_id': None,
                'husband_id': None,
                'husband_name': None,
                'ifa_consumed_7_days': 4,
                'is_pregnant': 1,
                'last_preg_tt': None,
                'last_preg_year': None,
                'lmp': datetime.date(2016, 11, 24),
                'married': None,
                'maternal_complications': None,
                'person_id': '8c5f8d3f-c6cd-4737-a994-2e494aeda05a',
                'preg_reg_date': datetime.date(2017, 4, 12),
                'total_ifa_tablets_received': -98,
                'tt_1': None,
                'tt_2': None,
                'tt_booster': None
            },
            ccs_case_details
        )

    def test_non_pregnant_mother_past_month_negative_ifa(self):
        update_bihar_api_table(date(2017, 5, 1))
        data, count = get_mother_details(
            month=date(2017, 5, 1).strftime("%Y-%m-%d"),
            state_id='st1',
            last_ccs_case_id=''
        )

        for case in data:
            if case['ccs_case_id'] == 'a87c92ec-d5a6-4dae-a8a1-14e7abf31441':
                ccs_case_details = case
                break

        self.assertEqual(
            {
                'add': datetime.date(2017, 5, 2),
                'anc_1': None,
                'anc_2': None,
                'anc_3': None,
                'anc_4': None,
                'causes_for_ifa': None,
                'ccs_case_id': 'a87c92ec-d5a6-4dae-a8a1-14e7abf31441',
                'edd': datetime.date(2017, 7, 12),
                'hb': None,
                'household_id': None,
                'husband_id': None,
                'husband_name': None,
                'ifa_consumed_7_days': 2,
                'is_pregnant': None,
                'last_preg_tt': None,
                'last_preg_year': None,
                'lmp': datetime.date(2016, 10, 5),
                'married': None,
                'maternal_complications': None,
                'person_id': 'c013cab2-e924-43f6-9a2d-cff137774229',
                'preg_reg_date': None,
                'total_ifa_tablets_received': -99,
                'tt_1': None,
                'tt_2': None,
                'tt_booster': None
            },
            ccs_case_details
        )

    def test_pregnant_mother_past_month_positive_ifa(self):
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
                "lmp": datetime.date(2016, 10, 2),
                "anc_1": datetime.date(2016, 10, 8),
                "anc_2": datetime.date(2016, 11, 7),
                "anc_3": datetime.date(2016, 12, 7),
                "anc_4": datetime.date(2017, 1, 6),
                "edd": datetime.date(2017, 7, 9),
                "total_ifa_tablets_received": 10,
                "ifa_consumed_7_days": 4,
                "causes_for_ifa": "side_effects",
                "maternal_complications": 'Discharge'
            },
            ccs_case_details
        )

    def test_non_pregnant_mother_past_month_positive_ifa(self):
        update_bihar_api_table(date(2017, 5, 1))
        data, count = get_mother_details(
            month=date(2017, 5, 1).strftime("%Y-%m-%d"),
            state_id='st1',
            last_ccs_case_id=''
        )

        for case in data:
            if case['ccs_case_id'] == 'f77d2181-5850-4675-9abe-2276acca4198':
                ccs_case_details = case
                break

        self.assertEqual(
            {
                'add': datetime.date(2017, 6, 1),
                'anc_1': None,
                'anc_2': None,
                'anc_3': None,
                'anc_4': None,
                'causes_for_ifa': None,
                'ccs_case_id': 'f77d2181-5850-4675-9abe-2276acca4198',
                'edd': datetime.date(2017, 7, 9),
                'hb': None,
                'household_id': None,
                'husband_id': None,
                'husband_name': None,
                'ifa_consumed_7_days': 4,
                'is_pregnant': 1,
                'last_preg_tt': None,
                'last_preg_year': None,
                'lmp': datetime.date(2016, 10, 2),
                'married': None,
                'maternal_complications': None,
                'person_id': 'ef12d6ce-a9af-4cf5-8459-0286432c5465',
                'preg_reg_date': datetime.date(2017, 4, 12),
                'total_ifa_tablets_received': None,
                'tt_1': None,
                'tt_2': None,
                'tt_booster': None
            },
            ccs_case_details
        )

    def test_non_pregnant_mother_current_month_positive_ifa(self):
        update_bihar_api_table(date(2017, 5, 1))
        data, count = get_mother_details(
            month=date(2017, 5, 1).strftime("%Y-%m-%d"),
            state_id='st1',
            last_ccs_case_id=''
        )

        for case in data:
            if case['ccs_case_id'] == 'f491263a-4846-4ffd-a64d-a6653c03dd03':
                ccs_case_details = case
                break

        self.assertEqual(
            {
                "household_id": None,
                "person_id": "1d3e45d5-bd58-487c-9f93-7da2cf67c8d7",
                "ccs_case_id": "f491263a-4846-4ffd-a64d-a6653c03dd03",
                "married": None,
                "husband_name": None,
                "husband_id": None,
                "last_preg_year": 14,
                "is_pregnant": None,
                "preg_reg_date": None,
                "tt_1": datetime.date(2017, 5, 31),
                'tt_2': datetime.date(2017, 6, 1),
                "tt_booster": datetime.date(2017, 6, 2),
                "hb": None,
                "add": datetime.date(2017, 3, 20),
                "last_preg_tt": None,
                "lmp": datetime.date(2016, 11, 1),
                "anc_1": datetime.date(2016, 11, 7),
                "anc_2": datetime.date(2016, 12, 7),
                "anc_3": datetime.date(2017, 1, 6),
                "anc_4": datetime.date(2017, 2, 5),
                "edd": datetime.date(2017, 8, 8),
                "total_ifa_tablets_received": 100,
                "ifa_consumed_7_days": 2,
                "causes_for_ifa": "dont_remember",
                "maternal_complications": "Discharge"
            },
            ccs_case_details
        )
