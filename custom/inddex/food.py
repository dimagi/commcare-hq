"""
This file contains the logic to generate the master dataset for the INDDEX reports

Overview
--------
Beneficiaries are asked about their diet in a "recall" session. This results in
a "foodrecall" case. Every food they mention results in the creation of a "food"
case that's a child of this foodrecall.

This dataset has a row for every food, with metadata about the recall session,
calculated nutritional information, and auditing columns reporting on what data
is or isn't available. Some of these foods are recipes, and their ingredients
appear as separate rows in the report.

Standard recipes have their ingredients enumerated in the "recipes" lookup
table. This dataset has additional rows inserted for each ingredient. These
rows are associated with the recipe case, but don't have a case of their own.

Nonstandard recipes are defined by the user and beneficiary during a recall
session. The ingredients of the recipe are entered as additional food cases and
linked to the recipe by `recipe_case_id`.

Beneficiaries may report eating a nonstandard recipe more than once, in which
case subsequent references point to the recipe definition with
already_reported_recipe_case_id and don't enumerate the ingredients again.


Components
----------
FoodData :: This is the interface to this dataset, it glues together all the
            component pieces and presents the result as a unified dataset.

FoodRow :: Class responsible for row-wise calculations and indicator definitions.

enrich_rows :: mutates FoodRow after the fact to calculate information related
               to ingredients in a recipe (which is otherwise outside the
               direct scope of FoodRow)
"""
import operator
import uuid
from collections import defaultdict
from functools import reduce

from memoized import memoized

from custom.inddex.ucr_data import FoodCaseData

from .const import (
    AGE_RANGES,
    FOOD_ITEM,
    NON_STANDARD_FOOD_ITEM,
    NON_STANDARD_RECIPE,
    STANDARD_RECIPE,
    ConvFactorGaps,
    FctGaps,
)
from .fixtures import FixtureAccessor

IN_UCR = 'in_ucr'
IN_FOOD_FIXTURE = 'in_food_fixture'
IS_RECALL_META = 'is_recall_meta'
CALCULATED_LATER = 'calculated_later'


class I:
    def __init__(self, slug, *tags):
        self.slug = slug
        tags = set(tags)
        self.in_ucr = IN_UCR in tags
        self.in_food_fixture = IN_FOOD_FIXTURE in tags
        self.is_recall_meta = IS_RECALL_META in tags
        self.is_calculated_later = CALCULATED_LATER in tags


# Indicator descriptions can be found here:
# https://docs.google.com/spreadsheets/d/1znPjfQSFEUFP_R_G8VYE-Bd5dg72k5sP-hZPuy-3RZo/edit
INDICATORS = [
    I('unique_respondent_id', IN_UCR, IS_RECALL_META),
    I('location_id', IN_UCR, IS_RECALL_META),
    I('respondent_id', IN_UCR, IS_RECALL_META),
    I('recall_case_id', IN_UCR, IS_RECALL_META),
    I('opened_date', IN_UCR, IS_RECALL_META),
    I('opened_by_username', IN_UCR, IS_RECALL_META),
    I('owner_name', IN_UCR, IS_RECALL_META),
    I('visit_date', IN_UCR, IS_RECALL_META),
    I('recall_status', IN_UCR, IS_RECALL_META),
    I('gender', IN_UCR, IS_RECALL_META),
    I('age_years_calculated', IN_UCR, IS_RECALL_META),
    I('age_months_calculated', IN_UCR, IS_RECALL_META),
    I('age_range', IS_RECALL_META),
    I('pregnant', IN_UCR, IS_RECALL_META),
    I('breastfeeding', IN_UCR, IS_RECALL_META),
    I('supplements', IN_UCR, IS_RECALL_META),
    I('urban_rural', IN_UCR, IS_RECALL_META),
    I('food_code', IN_UCR),
    I('food_name', IN_UCR, IN_FOOD_FIXTURE),
    I('recipe_name', IN_UCR, CALCULATED_LATER),
    I('caseid'),
    I('reference_food_code'),
    I('base_term_food_code', IN_UCR),
    I('food_type', IN_UCR, IN_FOOD_FIXTURE),
    I('include_in_analysis'),
    I('food_status', IN_UCR, IS_RECALL_META),
    I('eating_time', IN_UCR, IS_RECALL_META),
    I('time_block', IN_UCR, IS_RECALL_META),
    I('fao_who_gift_food_group_code'),
    I('fao_who_gift_food_group_description'),
    I('user_food_group'),
    I('already_reported_food', IN_UCR),
    I('already_reported_food_case_id', IN_UCR),
    I('already_reported_recipe', IN_UCR),
    I('already_reported_recipe_case_id', IN_UCR),
    I('already_reported_recipe_name', IN_UCR),
    I('is_ingredient', IN_UCR),
    I('recipe_case_id', IN_UCR),
    I('ingr_recipe_code'),
    I('ingr_fraction'),
    I('ingr_recipe_total_grams_consumed', CALCULATED_LATER),
    I('short_name', IN_UCR),
    I('food_base_term', IN_UCR, IN_FOOD_FIXTURE),
    I('tag_1', IN_UCR, IN_FOOD_FIXTURE),
    I('other_tag_1', IN_UCR),
    I('tag_2', IN_UCR, IN_FOOD_FIXTURE),
    I('other_tag_2', IN_UCR),
    I('tag_3', IN_UCR, IN_FOOD_FIXTURE),
    I('other_tag_3', IN_UCR),
    I('tag_4', IN_UCR, IN_FOOD_FIXTURE),
    I('other_tag_4', IN_UCR),
    I('tag_5', IN_UCR, IN_FOOD_FIXTURE),
    I('other_tag_5', IN_UCR),
    I('tag_6', IN_UCR, IN_FOOD_FIXTURE),
    I('other_tag_6', IN_UCR),
    I('tag_7', IN_UCR, IN_FOOD_FIXTURE),
    I('other_tag_7', IN_UCR),
    I('tag_8', IN_UCR, IN_FOOD_FIXTURE),
    I('other_tag_8', IN_UCR),
    I('tag_9', IN_UCR, IN_FOOD_FIXTURE),
    I('other_tag_9', IN_UCR),
    I('tag_10', IN_UCR, IN_FOOD_FIXTURE),
    I('other_tag_10', IN_UCR),
    I('conv_method_code', IN_UCR),
    I('conv_method_desc', IN_UCR),
    I('conv_option_code', IN_UCR),
    I('conv_option_desc', IN_UCR),
    I('measurement_amount', IN_UCR),
    I('conv_units', IN_UCR),
    I('portions', IN_UCR),
    I('nsr_conv_method_code_post_cooking', IN_UCR),
    I('nsr_conv_method_desc_post_cooking', IN_UCR),
    I('nsr_conv_option_code_post_cooking', IN_UCR),
    I('nsr_conv_option_desc_post_cooking', IN_UCR),
    I('nsr_measurement_amount_post_cooking', IN_UCR),
    I('nsr_consumed_cooked_fraction', IN_UCR),
    I('recipe_num_ingredients', CALCULATED_LATER),
    I('conv_factor_food_code'),
    I('conv_factor_base_term_food_code'),
    I('conv_factor_used'),
    I('conv_factor'),
    I('fct_food_code_exists'),
    I('fct_base_term_food_code_exists'),
    I('fct_reference_food_code_exists'),
    I('fct_data_used'),
    I('fct_code'),
    I('total_grams', CALCULATED_LATER),
    I('conv_factor_gap_code'),
    I('conv_factor_gap_desc'),
    I('fct_gap_code', CALCULATED_LATER),
    I('fct_gap_desc', CALCULATED_LATER),
]
_INDICATORS_BY_SLUG = {i.slug: i for i in INDICATORS}


class FoodRow:

    def __init__(self, ucr_row, fixtures, ingredient=None):
        self.uuid = uuid.uuid4()
        self.ucr_row = ucr_row
        self.fixtures = fixtures

        self._is_std_recipe_ingredient = bool(ingredient)
        if self._is_std_recipe_ingredient:
            self.food_code = ingredient.ingr_code
            self._set_ingredient_fields(ingredient)
        else:
            self.caseid = ucr_row['doc_id']
            self.food_code = ucr_row['food_code']

        self._set_composition()
        self._set_conversion_factors()

        self.is_recipe = self.food_type in (STANDARD_RECIPE, NON_STANDARD_RECIPE)
        self.include_in_analysis = not self.is_recipe

        self.measurement_amount = float(self.measurement_amount) if self.measurement_amount else None
        self.portions = float(self.portions) if self.portions else None
        self.nsr_consumed_cooked_fraction = (float(self.nsr_consumed_cooked_fraction)
                                             if self.nsr_consumed_cooked_fraction else None)
        self.enrichment_complete = False

    def _set_ingredient_fields(self, ingredient):
        if self._is_std_recipe_ingredient:
            self.is_ingredient = 'yes'
            self.recipe_case_id = self.ucr_row['doc_id']
            self.ingr_recipe_code = ingredient.recipe_code
            self.ingr_fraction = ingredient.ingr_fraction

            base_food = self.fixtures.foods_by_name.get(self.food_base_term)
            self.base_term_food_code = base_food.food_code if base_food else None

    def _set_composition(self):
        # Get the food composition corresponding to food_code, fall back to base_term_food_code
        fct = self.fixtures.food_compositions
        self.fct_food_code_exists = bool(self.food_code and self.food_code in fct)
        self.fct_base_term_food_code_exists = bool(self.base_term_food_code and self.base_term_food_code in fct)
        self.fct_code = None
        if self.fct_food_code_exists:
            self.fct_code = self.food_code
            self.fct_data_used = 'food_code'
        elif self.fct_base_term_food_code_exists:
            self.fct_code = self.base_term_food_code
            self.fct_data_used = 'base_term_food_code'

        if self.fct_code:
            self.composition = fct[self.fct_code]
            self.fao_who_gift_food_group_code = self.composition.fao_who_gift_food_group_code
            self.fao_who_gift_food_group_description = self.composition.fao_who_gift_food_group_description
            self.user_food_group = self.composition.user_defined_food_group

            self.reference_food_code = self.composition.reference_food_code_for_food_composition
            if self.fct_data_used == 'food_code' and self.reference_food_code:
                self.fct_data_used = 'reference_food_code'

        self.fct_reference_food_code_exists = bool(self.reference_food_code)

    def set_fct_gap(self, ingredients=None):
        if ingredients:
            for row in ingredients:
                row.set_fct_gap()

        self.fct_gap_code = FctGaps.NOT_AVAILABLE

        if self.food_type == FOOD_ITEM and self.fct_code:
            self.fct_gap_code = {
                'food_code': FctGaps.AVAILABLE,
                'base_term_food_code': FctGaps.BASE_TERM,
                'reference_food_code': FctGaps.REFERENCE,
            }[self.fct_data_used]

        if self.is_recipe and ingredients:
            if all(i.fct_gap_code == FctGaps.AVAILABLE for i in ingredients):
                self.fct_gap_code = FctGaps.AVAILABLE
            else:
                self.fct_gap_code = FctGaps.INGREDIENT_GAPS

        self.fct_gap_desc = FctGaps.get_description(self.fct_gap_code)

    def _set_conversion_factors(self):
        self.conv_factor_gap_code = ConvFactorGaps.NOT_AVAILABLE
        if self.food_type in (FOOD_ITEM, STANDARD_RECIPE) and self.conv_method_code:
            self.conv_factor_food_code = self.fixtures.conversion_factors.get(
                (self.food_code, self.conv_method_code, self.conv_option_code))
            self.conv_factor_base_term_food_code = self.fixtures.conversion_factors.get(
                (self.base_term_food_code, self.conv_method_code, self.conv_option_code))

            if self.conv_factor_food_code:
                self.conv_factor_used = 'food_code'
                self.conv_factor = self.conv_factor_food_code
                self.conv_factor_gap_code = ConvFactorGaps.AVAILABLE
            elif self.conv_factor_base_term_food_code:
                self.conv_factor_used = 'base_term_food_code'
                self.conv_factor = self.conv_factor_base_term_food_code
                self.conv_factor_gap_code = ConvFactorGaps.BASE_TERM

        self.conv_factor_gap_desc = ConvFactorGaps.get_description(self.conv_factor_gap_code)

    @property
    def age_range(self):
        if not self.age_months_calculated:
            return None
        for age_range in AGE_RANGES:
            if age_range.lower_bound <= getattr(self, age_range.column) < age_range.upper_bound:
                return age_range.name

    @property
    def recipe_id(self):
        if self.is_recipe:
            return self.caseid
        return self.recipe_case_id or 'NO_RECIPE'

    def get_nutrient_per_100g(self, nutrient_name):
        if self.fct_code:
            return self.composition.nutrients.get(nutrient_name)

    def get_nutrient_amt(self, nutrient_name):
        return _multiply(self.get_nutrient_per_100g(nutrient_name), self.total_grams, 0.01)

    def __getattr__(self, name):
        if name in _INDICATORS_BY_SLUG:
            indicator = _INDICATORS_BY_SLUG[name]
            if indicator.is_calculated_later:
                if not self.enrichment_complete:
                    raise AttributeError(f"{name} hasn't yet been set. It will be "
                                        "calculated outside the scope of FoodRow.")
                return None
            if self._is_std_recipe_ingredient:
                # If it's an indicator that hasn't been explicitly set, check if it can
                # be pulled from the food fixture or from the parent food case's UCR
                if indicator.in_food_fixture:
                    return getattr(self.fixtures.foods[self.food_code], indicator.slug)
                if indicator.is_recall_meta:
                    return self.ucr_row[indicator.slug]
                return None
            else:
                # If it's an indicator in the UCR that hasn't been explicitly set, return that val
                return self.ucr_row[indicator.slug] if indicator.in_ucr else None

        raise AttributeError(f"FoodRow has no definition for {name}")


def enrich_rows(recipe_id, rows):
    """Insert data possibly dependent on other rows in a recipe"""
    if recipe_id == 'NO_RECIPE':
        recipe = None
    else:
        recipe_possibilities = [row for row in rows if row.is_recipe]
        recipe = recipe_possibilities[0] if len(recipe_possibilities) == 1 else None

    if not recipe:
        for row in rows:
            row.total_grams = _multiply(row.measurement_amount, row.conv_factor, row.portions)
            row.set_fct_gap()
            row.enrichment_complete = True
    else:
        ingredients = [row for row in rows if row.uuid != recipe.uuid]
        total_grams = _calculate_total_grams(recipe, ingredients)
        recipe.set_fct_gap(ingredients)
        recipe.recipe_name = recipe.ucr_row['recipe_name']
        for row in [recipe] + ingredients:
            row.total_grams = total_grams[row.uuid]
            if row.is_recipe:
                row.recipe_num_ingredients = len(ingredients)
            if row.is_ingredient == 'yes':
                row.recipe_name = recipe.recipe_name
                if recipe.food_type == STANDARD_RECIPE:
                    row.ingr_recipe_total_grams_consumed = total_grams[recipe.uuid]
            row.enrichment_complete = True


def _calculate_total_grams(recipe, ingredients):
    if recipe.food_type == STANDARD_RECIPE:
        res = {}
        recipe_total = _multiply(recipe.measurement_amount, recipe.conv_factor, recipe.portions)
        res[recipe.uuid] = recipe_total
        for row in ingredients:
            res[row.uuid] = _multiply(recipe_total, row.ingr_fraction)
        return res
    else:  # NON_STANDARD_RECIPE
        res = {}
        for row in ingredients:
            res[row.uuid] = _multiply(row.measurement_amount, row.conv_factor,
                                      row.portions, recipe.nsr_consumed_cooked_fraction)
        try:
            res[recipe.uuid] = sum(res.values()) if res else None
        except TypeError:
            res[recipe.uuid] = None
        return res


class FoodData:
    """Generates the primary dataset for INDDEX reports.  See file docstring for more."""
    IN_MEMORY_FILTERS = ['gap_type', 'gap_code', 'fao_who_gift_food_group_description', 'food_type']
    FILTERABLE_COLUMNS = IN_MEMORY_FILTERS + FoodCaseData.FILTERABLE_COLUMNS

    def __init__(self, domain, *, datespan, filter_selections):
        for slug in filter_selections:
            if slug not in self.FILTERABLE_COLUMNS:
                raise AssertionError(f"{slug} is not a valid filter slug")

        self.fixtures = FixtureAccessor(domain)
        self._in_memory_filter_selections = {
            slug: filter_selections[slug] for slug in self.IN_MEMORY_FILTERS
            if slug in filter_selections
        }
        self.selected_gap_type = self._in_memory_filter_selections.get('gap_type')
        self._ucr = FoodCaseData({
            'domain': domain,
            'startdate': str(datespan.startdate),
            'enddate': str(datespan.enddate),
            **{k: v for k, v in filter_selections.items()
               if k in FoodCaseData.FILTERABLE_COLUMNS}
        })

    @classmethod
    def from_request(cls, domain, request):
        return cls(
            domain,
            datespan=request.datespan,
            filter_selections={'owner_id': request.GET.getlist('owner_id'),
                               **{k: request.GET.get(k)
                                  for k in cls.FILTERABLE_COLUMNS if k != 'owner_id'}}
        )

    def _matches_in_memory_filters(self, row):
        # If a gap type is specified, show only rows with gaps of that type
        gap_type = self.selected_gap_type
        if gap_type == ConvFactorGaps.slug and row.conv_factor_gap_code == ConvFactorGaps.AVAILABLE:
            return False
        if gap_type == FctGaps.slug and row.fct_gap_code == FctGaps.AVAILABLE:
            return False

        food_type = self._in_memory_filter_selections.get('food_type')
        if food_type and food_type != row.food_type:
            return False

        gap_code = self._in_memory_filter_selections.get('gap_code')
        # gap_code is from a drilldown filter, so gap_type must also be selected
        if gap_type and gap_code:
            if gap_type == ConvFactorGaps.slug and str(row.conv_factor_gap_code) != gap_code:
                return False
            if gap_type == FctGaps.slug and str(row.fct_gap_code) != gap_code:
                return False

        food_group = self._in_memory_filter_selections.get('fao_who_gift_food_group_description')
        if food_group and food_group != row.fao_who_gift_food_group_description:
            return False

        return True

    @property
    @memoized
    def rows(self):
        rows_by_recipe = defaultdict(list)

        for ucr_row in self._ucr.get_data():
            food = FoodRow(ucr_row, self.fixtures)
            rows_by_recipe[food.recipe_id].append(food)

            if food.food_type == STANDARD_RECIPE:
                for ingredient_data in self.fixtures.recipes[food.food_code]:
                    ingr_row = FoodRow(ucr_row, self.fixtures, ingredient_data)
                    rows_by_recipe[food.recipe_id].append(ingr_row)

        rows = []
        for recipe_id, rows_in_recipe in rows_by_recipe.items():
            enrich_rows(recipe_id, rows_in_recipe)
            for row in rows_in_recipe:
                if self._matches_in_memory_filters(row):
                    rows.append(row)
        return rows


def _multiply(*args):
    try:
        return reduce(operator.mul, args)
    except TypeError:
        return None
