from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.specs import TypeProperty
from corehq.util.quickcache import quickcache
from dimagi.ext.jsonobject import JsonObject


class LocationTypeSpec(JsonObject):
    type = TypeProperty('location_type_name')

    def __call__(self, item, context=None):
        doc_id = item.get('_id', None)
        if not doc_id:
            return None

        return self.get_location_type(doc_id)

    @quickcache(['location_id'], timeout=600)
    def get_location_type(self, location_id):
        sql_location = SQLLocation.objects.filter(location_id=location_id)
        if sql_location:
            return sql_location[0].location_type.name
        else:
            return None


def location_type_name(spec, context):
    wrapped = LocationTypeSpec.wrap(spec)
    return wrapped
