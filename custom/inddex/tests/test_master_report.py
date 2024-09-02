import csv
import doctest
import os
from contextlib import ExitStack
from datetime import date

from django.test import SimpleTestCase, TestCase
from django.utils.functional import cached_property

from memoized import memoized
from unittest.mock import patch
from unmagic import fixture

from dimagi.utils.dates import DateSpan

import custom.inddex.reports.r4_nutrient_stats
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.fixtures.models import LookupTable
from corehq.apps.userreports.util import get_indicator_adapter, get_ucr_datasource_config_by_id
from corehq.form_processor.models import CommCareCase
from corehq.sql_db.util import get_db_aliases_for_partitioned_query

from ..example_data.data import (
    FOOD_CASE_TYPE,
    FOODRECALL_CASE_TYPE,
    _get_or_create_user,
    populate_inddex_domain,
)
from ..fixtures import FixtureAccessor
from ..food import INDICATORS, FoodData
from ..reports.r1_master_data import MasterData
from ..reports.r2a_gaps_summary import get_gaps_data as get_2a_gaps_data
from ..reports.r2b_gaps_detail import GapsByItemSummaryData, GapsDetailsData
from ..reports.r2b_gaps_detail import get_gaps_data as get_2b_gaps_data
from ..reports.r3_nutrient_intake import DailyIntakeData, IntakeData
from ..reports.r4_nutrient_stats import NutrientStatsData
from ..ucr_data import FoodCaseData

DOMAIN = 'inddex-reports-test'


def get_expected_report(filename):
    with open(os.path.join(os.path.dirname(__file__), 'data', filename)) as f:
        rows = list(csv.DictReader(f))

    # Swap out the external IDs in the test fixture for the real IDs
    case_ids_by_external_id = _get_case_ids_by_external_id()
    return [{
        key: case_ids_by_external_id[val] if val in case_ids_by_external_id else val
        for key, val in row.items()
    } for row in rows]


def _overwrite_report(filename, actual_report):
    """For use when making changes - force overwrites test data"""
    case_ids = CommCareCase.objects.get_case_ids_in_domain(DOMAIN)
    external_ids_by_case_id = {c.case_id: c.external_id
        for c in CommCareCase.objects.get_cases(case_ids)}
    rows = [[
        external_ids_by_case_id[val] if val in external_ids_by_case_id else val
        for val in row
    ] for row in actual_report.rows]

    with open(os.path.join(os.path.dirname(__file__), 'data', filename), 'w') as f:
        writer = csv.writer(f)
        writer.writerow(actual_report.headers)
        writer.writerows(rows)


@fixture(scope='module', autouse=__file__)
def inddex_domain():
    def on_exit(callback):
        cleanup.callback(with_db, callback)

    def with_db(func):
        with db_blocker.unblock():
            func()

    db_blocker = fixture("django_db_blocker")()
    with ExitStack() as cleanup:
        cleanup.callback(_get_case_ids_by_external_id.reset_cache)
        cleanup.callback(get_food_data.reset_cache)

        with db_blocker.unblock():
            domain = create_domain(name=DOMAIN)
            on_exit(domain.delete)

            with patch('corehq.apps.callcenter.data_source.get_call_center_domains', lambda: []):
                datasource_config_id = populate_inddex_domain(DOMAIN)
                config = get_ucr_datasource_config_by_id(datasource_config_id)

        on_exit(lambda: _get_or_create_user(domain.name, create=False).delete(None, None))
        on_exit(LookupTable.objects.filter(domain=domain.name).delete)
        on_exit(get_indicator_adapter(config).drop_table)

        for dbname in get_db_aliases_for_partitioned_query():
            on_exit(CommCareCase.objects.using(dbname).filter(domain=domain.name).delete)

        yield


@memoized
def get_food_data(*args, **kwargs):
    # This class takes a while to run.  Memoizing lets me share between tests
    return FoodData(DOMAIN, datespan=DateSpan(date(2020, 1, 1), date(2020, 4, 1)), filter_selections={})


@memoized
def _get_case_ids_by_external_id():
    case_ids = CommCareCase.objects.get_case_ids_in_domain(DOMAIN)
    return {c.external_id: c.case_id for c in CommCareCase.objects.get_cases(case_ids)}


def sort_rows(rows):
    keys = ['recall_case_id', 'food_name', 'measurement_amount']
    return sorted(rows, key=lambda row: [row[k] for k in keys])


def food_names(rows):
    return [r['food_name'] for r in rows]


class TestSetupUtils(TestCase):
    def test_cases_created(self):
        case_ids = CommCareCase.objects.get_case_ids_in_domain(DOMAIN)
        cases = CommCareCase.objects.get_cases(case_ids)

        self.assertEqual(len(cases), 18)
        self.assertTrue(all(
            case.parent.type == FOODRECALL_CASE_TYPE
            for case in cases if case.type == FOOD_CASE_TYPE
        ))

    def test_fixtures_created(self):
        data_types = LookupTable.objects.by_domain(DOMAIN).count()
        self.assertEqual(data_types, 6)


class TestUcrAdapter(TestCase):
    def test_data_source(self):
        expected = get_expected_report('data_source.csv')
        ucr_data = FoodCaseData({
            'domain': DOMAIN,
            'startdate': date(2020, 1, 1).isoformat(),
            'enddate': date(2020, 4, 1).isoformat(),
        }).get_data()
        self.assertItemsEqual(food_names(expected), food_names(ucr_data))

    def test_data_source_filter(self):
        expected = [r for r in get_expected_report('data_source.csv')
                    if r['breastfeeding'] == 'breastfeeding_yes']
        ucr_data = FoodCaseData({
            'domain': DOMAIN,
            'startdate': date(2020, 1, 1).isoformat(),
            'enddate': date(2020, 4, 1).isoformat(),
            'breastfeeding': ['breastfeeding_yes'],
            'age_range': ['lt50years', 'lt15years'],
        }).get_data()
        self.assertItemsEqual(food_names(expected), food_names(ucr_data))

    def test_age_filter(self):
        ucr_data = FoodCaseData({
            'domain': DOMAIN,
            'startdate': date(2020, 1, 1).isoformat(),
            'enddate': date(2020, 4, 1).isoformat(),
            'age_range': ['gte65years'],
        }).get_data()
        self.assertEqual([], ucr_data)

    def test_urban_rural(self):
        ucr_data = FoodCaseData({
            'domain': DOMAIN,
            'startdate': date(2020, 1, 1).isoformat(),
            'enddate': date(2020, 4, 1).isoformat(),
            'urban_rural': ['peri-urban', 'rural'],
        }).get_data()
        self.assertEqual([], ucr_data)


class TestFixtures(TestCase):
    @cached_property
    def fixtures_accessor(self):  # `fixtures` is a reserved property on TestCase
        return FixtureAccessor(DOMAIN)

    def test_recipes(self):
        ingredients = self.fixtures_accessor.recipes['10089']
        self.assertEqual(7, len(ingredients))
        for ingredient in ingredients:
            if ingredient.ingr_code == '450':
                self.assertEqual('10089', ingredient.recipe_code)
                self.assertEqual(0.01, ingredient.ingr_fraction)

    def test_food_list(self):
        food = self.fixtures_accessor.foods['63']
        self.assertEqual("Riz,blanc,grain entier,poli,cru", food.food_name)
        self.assertEqual("Riz", food.food_base_term)

    def test_food_compositions(self):
        composition = self.fixtures_accessor.food_compositions['63']
        self.assertEqual("Cereals and their products (1)", composition.fao_who_gift_food_group_description)
        self.assertEqual(70.3, composition.nutrients['water_g'])

    def test_conversion_factors(self):
        conversion_factor = self.fixtures_accessor.conversion_factors[('187', '40', '1')]
        self.assertEqual(59.3, conversion_factor)

    def test_languages(self):
        self.assertEqual('lang_1', self.fixtures_accessor.lang_code)


class TestMasterReport(TestCase):
    maxDiff = None

    def test_master_report(self):
        expected = sort_rows(get_expected_report('1_master.csv'))
        actual = sort_rows(self.run_new_report())
        self.assertEqual(food_names(expected), food_names(actual))

        nutrient_columns = [
            'energy_kcal_per_100g',
            'energy_kcal',
            'water_g_per_100g',
            'water_g',
            'protein_g_per_100g',
            'protein_g',
        ]
        columns = [c.slug for c in INDICATORS] + nutrient_columns
        for column in columns:
            self.assert_columns_equal(expected, actual, column)

    def run_new_report(self):
        report = MasterData(get_food_data())
        # _overwrite_report('1_master.csv', report); raise Exception
        return [dict(zip(report.headers, row)) for row in report.rows]

    def assert_columns_equal(self, expected_rows, actual_rows, column):
        differences = []
        # it's already been confirmed that rows line up
        for expected_row, actual_row in zip(expected_rows, actual_rows):
            if expected_row[column] != actual_row[column]:
                differences.append(
                    (expected_row['food_name'], expected_row[column], actual_row[column])
                )
        if differences:
            msg = f"Column '{column}' has errors:\n"
            for food, expected_val, actual_val in differences:
                msg += f"{food}: expected '{expected_val}', got '{actual_val}'\n"
            raise AssertionError(msg)


class TestInddexReports(TestCase):
    maxDiff = None

    def assert_reports_match(self, csv_filename, actual_report):
        # _overwrite_report(csv_filename, actual_report); raise Exception

        def to_string(row):
            return ' | '.join(f'{v:<25}' for v in row)

        expected_report = get_expected_report(csv_filename)
        self.assertEqual(list(expected_report[0].keys()), actual_report.headers)

        expected_rows = sorted(list(r.values()) for r in expected_report)
        actual_rows = sorted(actual_report.rows)
        for expected, actual in zip(expected_rows, actual_rows):
            if expected != actual:
                msg = (
                    "\nRow doesn't match:\n"
                    "\nHeaders:  {}"
                    "\nExpected: {}"
                    "\nActual:   {}"
                ).format(*map(to_string, [actual_report.headers, expected, actual]))
                self.assertEqual(expected, actual, msg)

    def test_2a_gaps_summary(self):
        with patch('custom.inddex.reports.r2a_gaps_summary.FoodData.from_request', get_food_data):
            cf_gaps_data, fct_gaps_data = get_2a_gaps_data(DOMAIN, None)

        self.assert_reports_match('2a_conv_factor_gaps_summary.csv', cf_gaps_data)
        self.assert_reports_match('2a_fct_gaps_summary.csv', fct_gaps_data)

    def test_2b_gaps_reports(self):
        gaps_data = get_2b_gaps_data(get_food_data())
        self.assert_reports_match('2b_gaps_by_item_summary.csv', GapsByItemSummaryData(gaps_data))
        self.assert_reports_match('2b_gaps_by_item_details.csv', GapsDetailsData(gaps_data))

    def test_3_intake(self):
        data = IntakeData(get_food_data())
        self.assert_reports_match('3_disaggr_intake_data_by_rspndnt.csv', data)

    def test_3_daily_intake(self):
        data = DailyIntakeData(get_food_data())
        self.assert_reports_match('3_aggr_daily_intake_by_rspndnt.csv', data)

    def test_4_nutrient_stats(self):
        data = NutrientStatsData(get_food_data())
        self.assert_reports_match('4_nutr_intake_summary_stats.csv', data)

    def test_sharing_filtered_food_data(self):
        # There should be no data with this filter selection
        food_data = FoodData(DOMAIN, datespan=DateSpan(date(2020, 1, 1), date(2020, 4, 1)),
                             filter_selections={'owner_id': ['not-a-user']})
        self.assertEqual([], list(IntakeData(food_data).rows))
        self.assertEqual([], list(DailyIntakeData(food_data).rows))


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(custom.inddex.reports.r4_nutrient_stats)
        self.assertEqual(results.failed, 0)
