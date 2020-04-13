from datetime import date

from django.test import TestCase
from django.utils.functional import cached_property

from mock import patch

from dimagi.utils.dates import DateSpan

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.fixtures.dbaccessors import (
    count_fixture_items,
    get_fixture_data_types,
)
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.test_utils import require_db_context

from ..example_data.data import (
    FOOD_CASE_TYPE,
    FOODRECALL_CASE_TYPE,
    get_expected_report,
    populate_inddex_domain,
)
from ..fixtures import FixtureAccessor
from ..food import INDICATORS, FoodData
from ..reports.master_data import MasterData
from ..ucr_data import FoodCaseData

DOMAIN = 'inddex-reports-test'


@require_db_context
def setUpModule():
    create_domain(name=DOMAIN)
    try:
        with patch('corehq.apps.callcenter.data_source.get_call_center_domains', lambda: []):
            populate_inddex_domain(DOMAIN)
    except Exception:
        tearDownModule()
        raise


@require_db_context
def tearDownModule():
    Domain.get_by_name(DOMAIN).delete()


def sort_rows(rows):
    keys = ['recall_case_id', 'food_name', 'measurement_amount']
    return sorted(rows, key=lambda row: [row[k] for k in keys])


def food_names(rows):
    return [r['food_name'] for r in rows]


class TestSetupUtils(TestCase):
    def test_cases_created(self):
        accessor = CaseAccessors(DOMAIN)
        case_ids = accessor.get_case_ids_in_domain()
        cases = list(accessor.get_cases(case_ids))

        self.assertEqual(len(cases), 18)
        self.assertTrue(all(
            case.parent.type == FOODRECALL_CASE_TYPE
            for case in cases if case.type == FOOD_CASE_TYPE
        ))

    def test_fixtures_created(self):
        # Note, this is actually quite slow - might want to drop
        data_types = get_fixture_data_types(DOMAIN)
        self.assertEqual(len(data_types), 5)
        self.assertItemsEqual(
            [(dt.tag, count_fixture_items(DOMAIN, dt._id)) for dt in data_types],
            [('recipes', 384),
             ('food_list', 1130),
             ('food_composition_table', 1042),
             ('conv_factors', 2995),
             ('nutrients_lookup', 152)]
        )


class TestUcrAdapter(TestCase):
    def test_data_source(self):
        # Only the rows with case IDs will appear in the UCR
        expected = [r for r in get_expected_report() if r['caseid']]
        ucr_data = FoodCaseData({
            'domain': DOMAIN,
            'startdate': date(2020, 1, 1).isoformat(),
            'enddate': date(2020, 4, 1).isoformat(),
            'case_owners': '',
            'recall_status': '',
        }).get_data()
        self.assertItemsEqual(food_names(expected), food_names(ucr_data))


class TestFixtures(TestCase):
    @cached_property
    def fixtures_accessor(self):  # `fixtures` is a reserved property on TestCase
        return FixtureAccessor(DOMAIN)

    def test_recipes(self):
        ingredients = self.fixtures_accessor.recipes['10089']
        self.assertEqual(7, len(ingredients))
        for ingredient in ingredients:
            if ingredient.ingr_code == '450':
                self.assertEqual("Okra sauce", ingredient.recipe_descr)
                self.assertEqual("Potash,solid", ingredient.ingr_descr)
                self.assertEqual(0.01, ingredient.ingr_fraction)

    def test_food_list(self):
        food = self.fixtures_accessor.foods['10']
        self.assertEqual("Millet flour", food.food_name)
        self.assertEqual("Millet flour", food.food_base_term)

    def test_food_compositions(self):
        composition = self.fixtures_accessor.food_compositions['10']
        self.assertEqual("Millet flour", composition.survey_base_terms_and_food_items)
        self.assertEqual(367, composition.nutrients['energy_kcal'])
        self.assertEqual(9.1, composition.nutrients['water_g'])

    def test_conversion_factors(self):
        conversion_factor = self.fixtures_accessor.conversion_factors[('10', '52', '')]
        self.assertEqual(0.61, conversion_factor)


class TestNewReport(TestCase):
    maxDiff = None

    def test_new_report(self):
        expected = sort_rows(self.get_expected_rows())
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

    def get_expected_rows(self):
        # Swap out the external IDs in the test fixture for the real IDs
        accessor = CaseAccessors(DOMAIN)
        case_ids = accessor.get_case_ids_in_domain()
        case_ids_by_external_id = {c.external_id: c.case_id
                                   for c in accessor.get_cases(case_ids)}

        def substitute_real_ids(row):
            return {
                key: case_ids_by_external_id[val] if val in case_ids_by_external_id else val
                for key, val in row.items()
            }

        return map(substitute_real_ids, get_expected_report())

    def run_new_report(self):
        data = FoodData(DOMAIN, datespan=DateSpan(date(2020, 1, 1), date(2020, 4, 1)))
        report = MasterData(data)
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
