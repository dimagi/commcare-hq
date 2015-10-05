from corehq.apps.userreports.specs import TypeProperty
from dimagi.ext.jsonobject import JsonObject


class LocationTypeSepc(JsonObject):
    type = TypeProperty('location_type_name')

    def __call__(self, item, context=None):
        try:
            doc_id = item['_id']
            from corehq.apps.locations.models import SQLLocation
            sql_location = SQLLocation.objects.filter(location_id=doc_id)
            return sql_location[0].location_type.name
        except KeyError:
            return None


def location_type_name(spec, context):
    wrapped = LocationTypeSepc.wrap(spec)
    return wrapped
