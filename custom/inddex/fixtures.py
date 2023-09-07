from collections import defaultdict

from django.utils.functional import cached_property

from attr import attrib, attrs, fields_dict

from corehq.apps.fixtures.models import LookupTable, LookupTableRow


class InddexFixtureError(Exception):
    pass


def _wrap(FixtureClass, kwargs):
    try:
        return FixtureClass(**{k: v for k, v in kwargs.items()
                               if k in fields_dict(FixtureClass)})
    except Exception as e:
        raise InddexFixtureError(f"Error loading lookup table '{FixtureClass.table_name}': {e}")


@attrs(kw_only=True, frozen=True)
class RecipeIngredient:
    table_name = 'recipes'
    recipe_code = attrib()
    ingr_code = attrib()
    ingr_fraction = attrib(converter=float)


@attrs(kw_only=True, frozen=True)
class Food:
    table_name = 'food_list'
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
    table_name = 'food_composition_table'
    food_code = attrib()
    user_defined_food_group = attrib()
    fao_who_gift_food_group_code = attrib()
    fao_who_gift_food_group_description = attrib()
    reference_food_code_for_food_composition = attrib()
    nutrients: dict = attrib()


@attrs(kw_only=True, frozen=True)
class Nutrient:
    table_name = 'nutrients_lookup'
    nutrient_code = attrib()
    nutrient_name_unit = attrib()


@attrs(kw_only=True, frozen=True)
class ConversionFactor:
    table_name = 'conv_factors'
    food_code = attrib()
    conv_method = attrib()
    conv_option = attrib()
    conv_factor = attrib(converter=lambda x: float(x) if x else None)


@attrs(kw_only=True, frozen=True)
class Language:
    table_name = 'languages'
    lang_code = attrib()
    is_primary = attrib()


class FixtureAccessor:
    def __init__(self, domain):
        self.domain = domain

    @cached_property
    def _data_types_ids(self):
        return {
            table.tag: table.id
            for table in LookupTable.objects.by_domain(self.domain)
        }

    def _get_fixture_dicts(self, data_type_tag):
        data_type_id = self._data_types_ids[data_type_tag]
        for item in LookupTableRow.objects.iter_rows(self.domain, table_id=data_type_id):
            yield {name: vals[0].value for name, vals in item.fields.items()}

    @cached_property
    def recipes(self):
        """Lists of recipe ingredients by recipe_code"""
        recipes = defaultdict(list)
        for item_dict in self._get_fixture_dicts(RecipeIngredient.table_name):
            # The fixture contains duplicate entries for each language.
            if item_dict.pop('iso_code') == 'en':
                ingredient = _wrap(RecipeIngredient, item_dict)
                recipes[ingredient.recipe_code].append(ingredient)
        return recipes

    def _localize(self, col_name):
        if self.lang_code == 'lang_0':
            return col_name
        return f'{col_name}_{self.lang_code}'

    @cached_property
    def foods(self):
        """Food items by food_code"""
        foods = {}
        for item_dict in self._get_fixture_dicts(Food.table_name):
            item_dict['food_name'] = item_dict[self._localize('food_name')]
            item_dict['food_base_term'] = item_dict[self._localize('food_base_term')]
            food = _wrap(Food, item_dict)
            foods[food.food_code] = food
        return foods

    @cached_property
    def foods_by_name(self):
        return {food.food_name: food for food in self.foods.values()}

    @cached_property
    def _nutrients(self):
        return [
            _wrap(Nutrient, item_dict)
            for item_dict in self._get_fixture_dicts(Nutrient.table_name)
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
        for item_dict in self._get_fixture_dicts(FoodComposition.table_name):
            nutrients = {}
            composition_dict = {}
            for k, v in item_dict.items():
                if k.startswith('nut_'):
                    nutrients[self._nutrient_names_by_code[k]] = _to_float(v)
                else:
                    composition_dict[k] = v
            food = _wrap(FoodComposition, {'nutrients': nutrients, **composition_dict})
            foods[food.food_code] = food
        return foods

    @cached_property
    def conversion_factors(self):
        conversion_factors = (_wrap(ConversionFactor, item_dict)
                              for item_dict in self._get_fixture_dicts(ConversionFactor.table_name))
        return {
            (cf.food_code, cf.conv_method, cf.conv_option): cf.conv_factor for cf in conversion_factors
        }

    @cached_property
    def lang_code(self):
        languages = (_wrap(Language, item_dict)
                     for item_dict in self._get_fixture_dicts(Language.table_name))
        primary = [l.lang_code for l in languages if l.is_primary == 'yes']
        return primary[0] if primary else 'lang_1'


def _to_float(v):
    try:
        return float(v)
    except ValueError:
        return None
