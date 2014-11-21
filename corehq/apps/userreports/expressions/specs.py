from jsonobject import JsonObject, StringProperty, ListProperty
from corehq.apps.userreports.getters import DictGetter, NestedDictGetter
from corehq.apps.userreports.specs import TypeProperty


class PropertyNameMatchGetterSpec(JsonObject):
    type = TypeProperty('property_name_match')
    property_name = StringProperty(required=True)

    @property
    def getter(self):
        return DictGetter(self.property_name)


class PropertyPathMatchGetterSpec(JsonObject):
    type = TypeProperty('property_path_match')
    property_path = ListProperty(unicode, required=True)

    @property
    def getter(self):
        return NestedDictGetter(self.property_path)
