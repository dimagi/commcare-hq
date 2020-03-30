from datetime import datetime

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
    I('water_G_per_100g'),
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

    def __init__(self, food_code, ucr_row, fixtures):
        self.food_code = food_code
        self.ucr_row = ucr_row
        self.fixtures = fixtures

        self._set_composition()
        self._set_conversion_factors()

    def _set_composition(self):
        # Get the food composition corresponding to food_code, fall back to base_term_food_code
        fct = self.fixtures.food_compositions
        self.fct_food_code_exists = bool(self.food_code and self.food_code in fct)
        self.fct_base_term_food_code_exists = bool(self.base_term_food_code and self.base_term_food_code in fct)
        if self.fct_food_code_exists:
            self.composition = fct[self.food_code]
            self.fct_data_used = 'food_code'
        elif self.fct_base_term_food_code_exists:
            self.composition = fct[self.base_term_food_code]
            self.fct_data_used = 'food_code'
        else:
            self.composition = None

        if self.composition:
            self.fao_who_gift_food_group_code = self.composition.fao_who_gift_food_group_code
            self.fao_who_gift_food_group_description = self.composition.fao_who_gift_food_group_description
            self.user_food_group = self.composition.user_defined_food_group
            self.reference_food_code = self.composition.reference_food_code_for_food_composition

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
    def include_in_analysis(self):
        return self.food_type not in (STANDARD_RECIPE, NON_STANDARD_RECIPE)  # recipes are excluded

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

    def as_list(self):

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

        return [_format(getattr(self, column.slug)) for column in INDICATORS]


class FoodCaseRow(FoodRow):
    """A food item directly corresponding to a case in the UCR"""

    def __init__(self, ucr_row, fixtures):
        super().__init__(ucr_row['food_code'], ucr_row, fixtures)
        self.caseid = ucr_row['doc_id']

    def __getattr__(self, name):
        # If it's an indicator in the UCR that hasn't been explicitly set, return that val
        if name in _INDICATORS_BY_SLUG:
            indicator = _INDICATORS_BY_SLUG[name]
            return self.ucr_row[indicator.slug] if indicator.in_ucr else None
        raise AttributeError(f"FoodCaseRow has no definition for {name}")


class RecipeIngredientRow(FoodRow):
    """A food item inferred from a recipe"""
    is_ingredient = "yes"

    def __init__(self, ucr_row, fixtures, ingredient):
        # ucr_row is data from the parent food case
        # ingredient is static info for this ingredient from the recipes fixture
        super().__init__(ingredient.ingr_code, ucr_row, fixtures)

        self.recipe_name = ucr_row['recipe_name']
        self.recipe_case_id = ucr_row['doc_id']
        self.ingr_recipe_code = ingredient.recipe_code
        self.ingr_fraction = ingredient.ingr_fraction

        base_food = self.fixtures.foods_by_name.get(self.food_base_term)
        self.base_term_food_code = base_food.food_code if base_food else None

    def __getattr__(self, name):
        # If it's an indicator that hasn't been explicitly set, check if it can
        # be pulled from the food fixture or from the parent food case's UCR
        if name in _INDICATORS_BY_SLUG:
            indicator = _INDICATORS_BY_SLUG[name]
            if indicator.in_food_fixture:
                return getattr(self.fixtures.foods[self.food_code], indicator.slug)
            if indicator.is_recall_meta:
                return self.ucr_row[indicator.slug]
            return None
        raise AttributeError(f"RecipeIngredientRow has no definition for {name}")


class FoodData:
    def __init__(self, domain, ucr_rows):
        self.ucr_rows = ucr_rows
        self.fixtures = FixtureAccessor(domain)

    @property
    def headers(self):
        return [i.slug for i in INDICATORS]

    @property
    def rows(self):
        for ucr_row in self.ucr_rows:
            food = FoodCaseRow(ucr_row, self.fixtures)
            yield food.as_list()
            if food.food_type == STANDARD_RECIPE:
                for ingredient_data in self.fixtures.recipes[food.food_code]:
                    ingr_row = RecipeIngredientRow(ucr_row, self.fixtures, ingredient_data)
                    yield ingr_row.as_list()
