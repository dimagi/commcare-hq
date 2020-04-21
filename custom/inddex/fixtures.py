from collections import defaultdict

from django.utils.functional import cached_property

from attr import attrib, attrs

from corehq.apps.fixtures.dbaccessors import (
    get_fixture_data_types,
    iter_fixture_items_for_data_type,
)


@attrs(kw_only=True, frozen=True)
class RecipeIngredient:
    recipe_code = attrib()
    recipe_descr = attrib()
    recipe_type = attrib()
    recipe_type_descr = attrib()
    ingr_code = attrib()
    ingr_descr = attrib()
    ingr_fraction = attrib(converter=float)
    ingr_fraction_type = attrib()


@attrs(kw_only=True, frozen=True)
class Food:
    food_code = attrib()
    food_type = attrib()
    food_name = attrib()
    food_base_term = attrib()
    tag_1 = attrib()
    tag_2 = attrib()
    tag_3 = attrib()
    tag_4 = attrib()
    tag_5 = attrib()
    tag_6 = attrib()
    tag_7 = attrib()
    tag_8 = attrib()
    tag_9 = attrib()
    tag_10 = attrib()


@attrs(kw_only=True, frozen=True)
class FoodComposition:
    food_code = attrib()
    foodex2_code = attrib()
    foodex2_code_description = attrib()
    user_defined_food_group = attrib()
    fao_who_gift_food_group_code = attrib()
    fao_who_gift_food_group_description = attrib()
    fao_who_gift_nutrition_sub_group_code = attrib()
    fao_who_gift_nutrition_sub_group_description = attrib()
    fct_food_name = attrib()
    survey_base_terms_and_food_items = attrib()
    reference_food_code_for_food_composition = attrib()
    scientific_name = attrib()
    fct_source_description = attrib()
    yield_factor = attrib()
    yield_source_descr = attrib()
    retention_factor = attrib()
    retention_source_description = attrib()
    additional_details = attrib()
    additional_details_on_nutrients = attrib()
    nutrients: dict = attrib()


@attrs(kw_only=True, frozen=True)
class Nutrient:
    nutrient_code = attrib()
    nutrient_name = attrib()
    nutrient_name_unit = attrib()
    unit = attrib()


@attrs(kw_only=True, frozen=True)
class ConversionFactor:
    food_code = attrib()
    conv_method = attrib()
    conv_option = attrib()
    conv_factor = attrib(converter=lambda x: float(x) if x else None)
    energy_kcal = attrib(converter=float)


class FixtureAccessor:
    def __init__(self, domain):
        self.domain = domain

    @cached_property
    def _data_types(self):
        return {dt.tag: dt for dt in get_fixture_data_types(self.domain)}

    def _get_fixture_dicts(self, data_type_tag):
        data_type_id = self._data_types[data_type_tag].get_id
        for item in iter_fixture_items_for_data_type(self.domain, data_type_id):
            yield {field_name: field_list.field_list[0].field_value
                   for field_name, field_list in item.fields.items()}

    @cached_property
    def recipes(self):
        """Lists of recipe ingredients by recipe_code"""
        recipes = defaultdict(list)
        for item_dict in self._get_fixture_dicts('recipes'):
            # The fixture contains duplicate entries for each language.
            if item_dict.pop('iso_code') == 'en':
                ingredient = RecipeIngredient(**item_dict)
                recipes[ingredient.recipe_code].append(ingredient)
        return recipes

    @cached_property
    def foods(self):
        """Food items by food_code"""
        foods = {}
        for item_dict in self._get_fixture_dicts('food_list'):
            # A bunch of columns are duplicated - like food_name_lang_3
            item_dict = {k: v for k, v in item_dict.items() if '_lang_' not in k}
            food = Food(**item_dict)
            foods[food.food_code] = food
        return foods

    @cached_property
    def foods_by_name(self):
        return {food.food_name: food for food in self.foods.values()}

    @cached_property
    def _nutrients(self):
        return [
            Nutrient(**item_dict)
            for item_dict in self._get_fixture_dicts('nutrients_lookup')
        ]

    @cached_property
    def nutrient_names(self):
        return [n.nutrient_name_unit for n in self._nutrients]

    @cached_property
    def _nutrient_names_by_code(self):
        return {n.nutrient_code: n.nutrient_name_unit for n in self._nutrients}

    @cached_property
    def food_compositions(self):
        foods = {}
        for item_dict in self._get_fixture_dicts('food_composition_table'):
            nutrients = {}
            composition_dict = {}
            for k, v in item_dict.items():
                if k.startswith('nut_'):
                    nutrients[self._nutrient_names_by_code[k]] = _to_float(v)
                else:
                    composition_dict[k] = v
            food = FoodComposition(nutrients=nutrients, **composition_dict)
            foods[food.food_code] = food
        return foods

    @cached_property
    def conversion_factors(self):
        conversion_factors = (ConversionFactor(**item_dict)
                              for item_dict in self._get_fixture_dicts('conv_factors'))
        return {
            (cf.food_code, cf.conv_method, cf.conv_option): cf.conv_factor for cf in conversion_factors
        }


def _to_float(v):
    try:
        return float(v)
    except ValueError:
        return None
