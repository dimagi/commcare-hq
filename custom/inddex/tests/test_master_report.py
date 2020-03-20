from datetime import date

from django.test import TestCase

from mock import patch

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.fixtures.dbaccessors import (
    count_fixture_items,
    get_fixture_data_types,
)
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from ..example_data.data import (
    FOOD_CASE_TYPE,
    FOODRECALL_CASE_TYPE,
    get_expected_report,
    populate_inddex_domain,
)
from ..food import FoodData, FoodRow
from ..ucr.adapters import FoodCaseData
from ..ucr.data_providers.master_data_file_data import MasterDataFileData


class TestMasterReport(TestCase):
    maxDiff = None
    domain = 'inddex-reports-test'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(name=cls.domain)
        with patch('corehq.apps.callcenter.data_source.get_call_center_domains', lambda: []):
            populate_inddex_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_cases_created(self):
        accessor = CaseAccessors(self.domain)
        case_ids = accessor.get_case_ids_in_domain()
        cases = list(accessor.get_cases(case_ids))

        self.assertEqual(len(cases), 18)
        self.assertTrue(all(
            case.parent.type == FOODRECALL_CASE_TYPE
            for case in cases if case.type == FOOD_CASE_TYPE
        ))

    def test_fixtures_created(self):
        # Note, this is actually quite slow - might want to drop
        data_types = get_fixture_data_types(self.domain)
        self.assertEqual(len(data_types), 4)
        self.assertItemsEqual(
            [(dt.tag, count_fixture_items(self.domain, dt._id)) for dt in data_types],
            [('recipes', 384),
             ('food_list', 1130),
             ('food_composition_table', 1042),
             ('conv_factors', 2995)]
        )

    def test_old_report(self):
        expected = get_expected_report()
        # exclude rows not pulled from cases for now
        expected = [r for r in get_expected_report() if r['caseid']]

        actual = self.run_report()
        self.assertItemsEqual(expected[0].keys(), actual[0].keys())  # compare headers

        # sort uniformly for comparison
        expected = self.sort_rows(expected)
        actual = self.sort_rows(actual)

        self.assert_same_foods_present(expected, actual)
        for expected_row, actual_row in zip(expected, actual):
            pass
            # self.assert_same_column_vals(expected_row, actual_row, expected_row.keys())

    @staticmethod
    def sort_rows(rows):
        return sorted(rows, key=lambda row: (row['food_name'], row['measurement_amount']))

    def run_report(self):
        report_data = MasterDataFileData({
            'domain': self.domain,
            'startdate': date(2020, 1, 1).isoformat(),
            'enddate': date(2020, 4, 1).isoformat(),
            'case_owners': '',
            'gap_type': '',
            'recall_status': '',
        })
        headers = [h.html for h in report_data.headers]
        return [dict(zip(headers, row)) for row in report_data.rows]

    def assert_same_foods_present(self, expected, actual):
        self.assertEqual(
            [r['food_name'] for r in expected],
            [r['food_name'] for r in actual],
        )

    def assert_same_column_vals(self, expected_row, actual_row, columns):
        def get_differing_columns(expected_row, actual_row):
            for header in columns:
                expected = expected_row[header]
                actual = actual_row.get(header, 'MISSING')
                if expected != actual:
                    yield (header, expected, actual)

        differing_cols = list(get_differing_columns(expected_row, actual_row))
        if differing_cols:
            food_name = expected_row['food_name']
            msg = f"Incorrect columns in row for {food_name}:"
            for header, expected, actual in differing_cols:
                msg += f"\n{header}: expected '{expected}' got '{actual}'"
            self.assertTrue(False, msg)

    def test_data_source(self):
        # Only the rows with case IDs will appear in the UCR
        expected = self.sort_rows(r for r in get_expected_report() if r['caseid'])
        ucr_data = self.sort_rows(self.get_ucr_data())
        self.assert_same_foods_present(expected, ucr_data)

    def get_ucr_data(self):
        return FoodCaseData({
            'domain': self.domain,
            'startdate': date(2020, 1, 1).isoformat(),
            'enddate': date(2020, 4, 1).isoformat(),
            'case_owners': '',
            'recall_status': '',
        }).get_data()

    def test_new_report(self):
        expected = self.sort_rows(self.get_expected_rows())
        actual = self.sort_rows(self.run_new_report())
        self.assert_same_foods_present(expected, actual)
        columns_known_to_fail = {  # TODO address these columns
            'unique_respondent_id',
            'respondent_id',
            'opened_date',
            'recipe_name',
            'reference_food_code',
            'include_in_analysis',
            'time_block',
            'ingr_recipe_code',
            'nsr_conv_method_code_post_cooking',
            'nsr_conv_option_code_post_cooking',
            'nsr_conv_option_desc_post_cooking',
            'already_reported_food',
        }
        columns = [c for c in FoodRow._indicators_in_ucr  # for now, only ucr columns are correct
                   if c not in columns_known_to_fail]
        for expected_row, actual_row in zip(expected, actual):
            self.assert_same_column_vals(expected_row, actual_row, columns)

    def get_expected_rows(self):
        # Only the rows with case IDs currently appear
        # TODO insert remaining rows
        expected = [r for r in get_expected_report() if r['caseid']]

        # Swap out the external IDs in the test fixture for the real IDs
        accessor = CaseAccessors(self.domain)
        case_ids = accessor.get_case_ids_in_domain()
        case_ids_by_external_id = {c.external_id: c.case_id
                                   for c in accessor.get_cases(case_ids)}

        def substitute_real_ids(row):
            for id_col in ['recall_case_id', 'caseid']:
                row[id_col] = case_ids_by_external_id[row[id_col]]
            return row

        return map(substitute_real_ids, expected)

    def run_new_report(self):
        ucr_data = self.get_ucr_data()
        report = FoodData(ucr_data)
        return [dict(zip(report.headers, row)) for row in report.rows]
