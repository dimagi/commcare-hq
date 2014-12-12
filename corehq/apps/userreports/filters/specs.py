from jsonobject import JsonObject, StringProperty, ListProperty, DictProperty
from jsonobject.base import DefaultProperty
from corehq.apps.userreports.expressions.getters import getter_from_property_reference
from corehq.apps.userreports.operators import OPERATORS
from corehq.apps.userreports.specs import TypeProperty


class BaseFilterSpec(JsonObject):
    _allow_dynamic_properties = False


class BooleanExpressionFilterSpec(BaseFilterSpec):
    type = TypeProperty('boolean_expression')
    operator = StringProperty(choices=OPERATORS.keys())
    property_value = DefaultProperty(required=True)
    expression = DictProperty(required=True)


class PropertyMatchFilterSpec(BaseFilterSpec):
    type = TypeProperty('property_match')
    property_name = StringProperty()
    property_path = ListProperty()
    property_value = DefaultProperty(required=True)

    @property
    def getter(self):
        return getter_from_property_reference(self)


class NotFilterSpec(BaseFilterSpec):
    type = TypeProperty('not')
    filter = DictProperty()  # todo: validators=FilterFactory.validate_spec


class NamedFilterSpec(BaseFilterSpec):
    type = TypeProperty('named')
    name = StringProperty(required=True)

