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
    iso_code = attrib()


class FixtureAccessor:
    def __init__(self, domain):
        self.domain = domain

    @cached_property
    def _data_types(self):
        return {dt.tag: dt for dt in get_fixture_data_types(self.domain)}

    def get_recipes(self):
        recipes_data_type = self._data_types['recipes']
        for item in iter_fixture_items_for_data_type(self.domain, recipes_data_type.get_id):
            item_dict = {field_name: field_list.field_list[0].field_value
                         for field_name, field_list in item.fields.items()}
            yield RecipeIngredient(**item_dict)
