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
