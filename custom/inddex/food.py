import operator
import uuid
from collections import defaultdict
from datetime import datetime
from functools import reduce

from django.utils.functional import cached_property

from .fixtures import FixtureAccessor

MISSING = ''

IN_UCR = 'in_ucr'
IN_FOOD_FIXTURE = 'in_food_fixture'
IS_RECALL_META = 'is_recall_meta'

# food_type options
FOOD_ITEM = 'food_item'
NON_STANDARD_FOOD_ITEM = 'non_std_food_item'
STANDARD_RECIPE = 'std_recipe'
NON_STANDARD_RECIPE = 'non_std_recipe'


class I:
    def __init__(self, slug, *tags):
        self.slug = slug
        tags = set(tags)
        self.in_ucr = IN_UCR in tags
        self.in_food_fixture = IN_FOOD_FIXTURE in tags
        self.is_recall_meta = IS_RECALL_META in tags


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
    I('recalled_date', IN_UCR, IS_RECALL_META),
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
    I('recipe_name', IN_UCR),
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
    I('ingr_recipe_total_grams_consumed'),
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
    I('recipe_num_ingredients'),
    I('conv_factor_food_code'),
    I('conv_factor_base_term_food_code'),
    I('conv_factor_used'),
    I('conv_factor'),
    I('fct_food_code_exists'),
    I('fct_base_term_food_code_exists'),
    I('fct_reference_food_code_exists'),
    I('fct_data_used'),
    I('fct_code'),
    I('total_grams'),
    I('energy_kcal_per_100g'),
    I('energy_kcal'),
    I('water_g_per_100g'),
    I('water_g'),
    I('protein_g_per_100g'),
    I('protein_g'),
    I('conv_factor_gap_code'),
    I('conv_factor_gap_desc'),
    I('fct_gap_code'),
    I('fct_gap_desc'),
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

    def _set_ingredient_fields(self, ingredient):
        if self._is_std_recipe_ingredient:
            self.is_ingredient = 'yes'
            self.recipe_name = self.ucr_row['recipe_name']
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

    def _set_conversion_factors(self):
        if self.food_type in (FOOD_ITEM, STANDARD_RECIPE) and self.conv_method_code:
            self.conv_factor_food_code = self.fixtures.conversion_factors.get(
                (self.food_code, self.conv_method_code, self.conv_option_code))
            self.conv_factor_base_term_food_code = self.fixtures.conversion_factors.get(
                (self.base_term_food_code, self.conv_method_code, self.conv_option_code))

            if self.conv_factor_food_code:
                self.conv_factor_used = 'food_code'
                self.conv_factor = self.conv_factor_food_code
            elif self.conv_factor_base_term_food_code:
                self.conv_factor_used = 'base_term_food_code'
                self.conv_factor = self.conv_factor_base_term_food_code

    @property
    def age_range(self):
        if self.age_months_calculated < 6:
            return "0-5.9 months"
        elif self.age_months_calculated < 60:
            return "06-59 months"
        elif self.age_years_calculated < 7:
            return "5-6 years"
        elif self.age_years_calculated < 11:
            return "7-10 years"
        elif self.age_years_calculated < 15:
            return "7-14 years"
        elif self.age_years_calculated < 50:
            return "15-49 years"
        elif self.age_years_calculated < 65:
            return "50-64 years"
        return "65+ years"

    @property
    def recipe_id(self):
        if self.is_recipe:
            return self.caseid
        return self.recipe_case_id or self.already_reported_recipe_case_id or 'NO_RECIPE'

    def __getattr__(self, name):
        if name in _INDICATORS_BY_SLUG:
            if self._is_std_recipe_ingredient:
                # If it's an indicator that hasn't been explicitly set, check if it can
                # be pulled from the food fixture or from the parent food case's UCR
                indicator = _INDICATORS_BY_SLUG[name]
                if indicator.in_food_fixture:
                    return getattr(self.fixtures.foods[self.food_code], indicator.slug)
                if indicator.is_recall_meta:
                    return self.ucr_row[indicator.slug]
                return None
            else:
                # If it's an indicator in the UCR that hasn't been explicitly set, return that val
                indicator = _INDICATORS_BY_SLUG[name]
                return self.ucr_row[indicator.slug] if indicator.in_ucr else None

        raise AttributeError(f"FoodRow has no definition for {name}")


class RecipeRowGenerator:
    """Contains all rows of a given recipe. Handles calculations outside the scope of a single row"""

    def __init__(self, recipe_id, rows):
        self._all_rows = rows

        recipe_possibilities = [row for row in rows if row.is_recipe]
        self._recipe_row = recipe_possibilities[0] if len(recipe_possibilities) == 1 else None
        self._recipe_ingredients = [row for row in rows if not row.is_recipe]

    def iter_rows(self):
        if not self._recipe_row:
            yield from _yield_non_recipe_rows(self._all_rows)
        else:
            for row in [self._recipe_row] + self._recipe_ingredients:
                yield [_format(self._get_val(row, column.slug)) for column in INDICATORS]

    def _get_val(self, row, slug):
        if slug == 'recipe_num_ingredients' and row.is_recipe:
            return len(self._recipe_ingredients)
        if slug == 'total_grams':
            return self._total_grams[row.uuid]
        if slug == 'ingr_recipe_total_grams_consumed':
            if row.is_ingredient == 'yes' and self._recipe_row.food_type == STANDARD_RECIPE:
                return self._total_grams[self._recipe_row.uuid]
        return getattr(row, slug)

    @cached_property
    def _total_grams(self):
        recipe = self._recipe_row
        if recipe.food_type == STANDARD_RECIPE:
            res = {}
            recipe_total = _multiply(recipe.measurement_amount, recipe.conv_factor, recipe.portions)
            res[recipe.uuid] = recipe_total
            for row in self._recipe_ingredients:
                res[row.uuid] = _multiply(recipe_total, row.ingr_fraction)
            return res

        else:  # NON_STANDARD_RECIPE
            res = {}

            for row in self._recipe_ingredients:
                res[row.uuid] = _multiply(row.measurement_amount, row.conv_factor,
                                          row.portions, recipe.nsr_consumed_cooked_fraction)
            try:
                res[recipe.uuid] = sum(res.values()) if res else None
            except TypeError:
                res[recipe.uuid] = None
            return res



class FoodData:
    def __init__(self, domain, ucr_rows):
        self.ucr_rows = ucr_rows
        self.fixtures = FixtureAccessor(domain)

    @property
    def headers(self):
        return [i.slug for i in INDICATORS]

    @property
    def rows(self):
        rows_by_recipe = defaultdict(list)

        for ucr_row in self.ucr_rows:
            food = FoodRow(ucr_row, self.fixtures)
            rows_by_recipe[food.recipe_id].append(food)

            if food.food_type == STANDARD_RECIPE:
                for ingredient_data in self.fixtures.recipes[food.food_code]:
                    ingr_row = FoodRow(ucr_row, self.fixtures, ingredient_data)
                    rows_by_recipe[food.recipe_id].append(ingr_row)

        for recipe_id, rows_in_recipe in rows_by_recipe.items():
            if recipe_id == 'NO_RECIPE':
                yield from _yield_non_recipe_rows(rows_in_recipe)
            else:
                yield from RecipeRowGenerator(recipe_id, rows_in_recipe).iter_rows()


def _yield_non_recipe_rows(rows):

    def _get_val(row, slug):
        if slug == 'total_grams':
            return _multiply(row.measurement_amount, row.conv_factor, row.portions)
        return getattr(row, slug)

    for row in rows:
        yield [_format(_get_val(row, column.slug)) for column in INDICATORS]


def _multiply(*args):
    try:
        return round(reduce(operator.mul, args), 2)
    except TypeError:
        return None


def _format(val):
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(val, bool):
        return "yes" if val else "no"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return str(int(val)) if val.is_integer() else str(val)
    if val is None:
        return MISSING
    return val
