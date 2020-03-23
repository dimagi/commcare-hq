from collections import defaultdict

from django.utils.functional import cached_property

from .fixtures import FixtureAccessor

ORDERED_INDICATORS = [
    'unique_respondent_id',
    'location_id',
    'respondent_id',
    'recall_case_id',
    'opened_date',
    'opened_by_username',
    'owner_name',
    'recalled_date',
    'recall_status',
    'gender',
    'age_years_calculated',
    'age_months_calculated',
    'age_range',
    'pregnant',
    'breastfeeding',
    'supplements',
    'urban_rural',
    'food_code',
    'food_name',
    'recipe_name',
    'caseid',
    'reference_food_code',
    'base_term_food_code',
    'food_type',
    'include_in_analysis',
    'food_status',
    'eating_time',
    'time_block',
    'fao_who_gift_food_group_code',
    'fao_who_gift_food_group_description',
    'user_food_group',
    'already_reported_food',
    'already_reported_food_case_id',
    'already_reported_recipe',
    'already_reported_recipe_case_id',
    'already_reported_recipe_name',
    'is_ingredient',
    'recipe_case_id',
    'ingr_recipe_code',
    'ingr_fraction',
    'ingr_recipe_total_grams_consumed',
    'short_name',
    'food_base_term',
    'tag_1',
    'other_tag_1',
    'tag_2',
    'other_tag_2',
    'tag_3',
    'other_tag_3',
    'tag_4',
    'other_tag_4',
    'tag_5',
    'other_tag_5',
    'tag_6',
    'other_tag_6',
    'tag_7',
    'other_tag_7',
    'tag_8',
    'other_tag_8',
    'tag_9',
    'other_tag_9',
    'tag_10',
    'other_tag_10',
    'conv_method_code',
    'conv_method_desc',
    'conv_option_code',
    'conv_option_desc',
    'measurement_amount',
    'conv_units',
    'portions',
    'nsr_conv_method_code_post_cooking',
    'nsr_conv_method_desc_post_cooking',
    'nsr_conv_option_code_post_cooking',
    'nsr_conv_option_desc_post_cooking',
    'nsr_measurement_amount_post_cooking',
    'nsr_consumed_cooked_fraction',
    'recipe_num_ingredients',
    'conv_factor_food_code',
    'conv_factor_base_term_food_code',
    'conv_factor_used',
    'conv_factor',
    'fct_food_code_exists',
    'fct_base_term_food_code_exists',
    'fct_reference_food_code_exists',
    'fct_data_used',
    'fct_code',
    'total_grams',
    'energy_kcal_per_100g',
    'energy_kcal',
    'water_G_per_100g',
    'water_g',
    'protein_g_per_100g',
    'protein_g',
    'conv_factor_gap_code',
    'conv_factor_gap_desc',
    'fct_gap_code',
    'fct_gap_desc',
]


class FoodRow:
    _indicators_in_ucr = [
        'unique_respondent_id', 'respondent_id', 'recall_case_id',
        'opened_date', 'opened_by_username', 'owner_name', 'recalled_date',
        'recall_status', 'gender', 'age_years_calculated',
        'age_months_calculated', 'pregnant', 'breastfeeding', 'supplements',
        'urban_rural', 'food_code', 'food_name', 'recipe_name',
        'reference_food_code', 'food_type', 'include_in_analysis',
        'food_status', 'eating_time', 'time_block', 'already_reported_food',
        'already_reported_food_case_id', 'is_ingredient', 'recipe_case_id',
        'ingr_recipe_code', 'short_name', 'food_base_term', 'tag_1',
        'other_tag_1', 'tag_2', 'other_tag_2', 'tag_3', 'other_tag_3', 'tag_4',
        'other_tag_4', 'tag_5', 'other_tag_5', 'tag_6', 'other_tag_6', 'tag_7',
        'other_tag_7', 'tag_8', 'other_tag_8', 'tag_9', 'other_tag_9',
        'tag_10', 'other_tag_10', 'conv_method_code', 'conv_method_desc',
        'conv_option_code', 'conv_option_desc', 'measurement_amount',
        'conv_units', 'portions', 'nsr_conv_method_code_post_cooking',
        'nsr_conv_option_code_post_cooking',
        'nsr_conv_option_desc_post_cooking',
        'nsr_measurement_amount_post_cooking',
    ]
    location_id = 'report'
    age_range = ''
    caseid = ''  # should just return doc_id
    base_term_food_code = ''
    fao_who_gift_food_group_code = ''
    fao_who_gift_food_group_description = ''
    user_food_group = ''
    already_reported_recipe = ''
    already_reported_recipe_case_id = ''
    already_reported_recipe_name = ''
    ingr_fraction = ''
    ingr_recipe_total_grams_consumed = ''
    nsr_conv_method_desc_post_cooking = ''  # TODO this one should be added to the UCR
    nsr_consumed_cooked_fraction = ''  # TODO this one should be added to the UCR
    recipe_num_ingredients = ''
    conv_factor_food_code = ''
    conv_factor_base_term_food_code = ''
    conv_factor_used = ''
    conv_factor = ''
    fct_food_code_exists = ''
    fct_base_term_food_code_exists = ''
    fct_reference_food_code_exists = ''
    fct_data_used = ''
    fct_code = ''
    total_grams = ''
    energy_kcal_per_100g = ''
    energy_kcal = ''
    water_G_per_100g = ''
    water_g = ''
    protein_g_per_100g = ''
    protein_g = ''
    conv_factor_gap_code = ''
    conv_factor_gap_desc = ''
    fct_gap_code = ''
    fct_gap_desc = ''

    def __init__(self, ucr_row):
        self.ucr_row = ucr_row
        for indicator in self._indicators_in_ucr:
            setattr(self, indicator, ucr_row[indicator])


class RecipeIngredientRow(FoodRow):
    def __init__(self, ucr_row, ingredient):
        # ucr_row is data from the parent food case, ingredient is for this ingredient
        super().__init__(ucr_row)
        self.ingredient = ingredient
        self.food_name = ingredient.ingr_descr


class FoodData:
    def __init__(self, domain, ucr_rows):
        self.ucr_rows = ucr_rows
        self.fixture_accessor = FixtureAccessor(domain)

    @property
    def headers(self):
        return ORDERED_INDICATORS

    @property
    def rows(self):
        for ucr_row in self.ucr_rows:
            food = FoodRow(ucr_row)
            yield [
                getattr(food, column) for column in ORDERED_INDICATORS
            ]
            if food.food_type == 'std_recipe':
                for ingredient_data in self._recipes[food.food_code]:
                    ingr_row = RecipeIngredientRow(ucr_row, ingredient_data)
                    yield [
                        getattr(ingr_row, column) for column in ORDERED_INDICATORS
                    ]

    @cached_property
    def _recipes(self):
        recipes = defaultdict(list)
        for ingredient in self.fixture_accessor.get_recipes():
            recipes[ingredient.recipe_code].append(ingredient)
        return recipes
