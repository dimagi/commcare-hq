from jsonobject import JsonObject, StringProperty, ListProperty
from corehq.apps.userreports.expressions.getters import DictGetter, NestedDictGetter
from corehq.apps.userreports.specs import TypeProperty


class PropertyNameGetterSpec(JsonObject):
    type = TypeProperty('property_name')
    property_name = StringProperty(required=True)

    @property
    def getter(self):
        return DictGetter(self.property_name)


class PropertyPathGetterSpec(JsonObject):
    type = TypeProperty('property_path')
    property_path = ListProperty(unicode, required=True)

    @property
    def getter(self):
        return NestedDictGetter(self.property_path)
