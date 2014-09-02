from jsonobject import JsonObject, StringProperty, ListProperty, BooleanProperty

# todo: all spec definitions will go here. moving them over piece meal when touched.
from corehq.apps.userreports.getters import DictGetter, NestedDictGetter


class RawIndicatorSpec(JsonObject):
    column_id = StringProperty(required=True)
    datatype = StringProperty(required=True)
    property_name = StringProperty()
    property_path = ListProperty()
    display_name = StringProperty()
    is_nullable = BooleanProperty(default=True)
    is_primary_key = BooleanProperty(default=False)

    @classmethod
    def wrap(cls, obj):
        if 'display_name' not in obj:
            obj['display_name'] = obj['column_id']
        return super(RawIndicatorSpec, cls).wrap(obj)

    @property
    def getter(self):
        if self.property_name:
            assert not self.property_path
            return DictGetter(property_name=self.property_name)
        else:
            assert self.property_path
            return NestedDictGetter(property_path=self.property_path)

