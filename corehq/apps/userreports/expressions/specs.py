from jsonobject import JsonObject, StringProperty, ListProperty, DictProperty
from jsonobject.base_properties import DefaultProperty
from corehq.apps.userreports.expressions.getters import DictGetter, NestedDictGetter
from corehq.apps.userreports.specs import TypeProperty


class ConstantGetterSpec(JsonObject):
    type = TypeProperty('constant')
    constant = DefaultProperty(required=True)

    @property
    def expression(self):
        return lambda item, context=None: self.constant


class PropertyNameGetterSpec(JsonObject):
    type = TypeProperty('property_name')
    property_name = StringProperty(required=True)

    @property
    def expression(self):
        return DictGetter(self.property_name)


class PropertyPathGetterSpec(JsonObject):
    type = TypeProperty('property_path')
    property_path = ListProperty(unicode, required=True)

    @property
    def expression(self):
        return NestedDictGetter(self.property_path)


class ConditionalExpressionSpec(JsonObject):
    type = TypeProperty('conditional')
    test = DictProperty(required=True)
    expression_if_true = DictProperty(required=True)
    expression_if_false = DictProperty(required=True)


class RootDocExpressionSpec(JsonObject):
    type = TypeProperty('root_doc')
    expression = DictProperty(required=True)
