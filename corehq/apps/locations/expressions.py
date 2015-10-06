from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import TypeProperty
from corehq.util.quickcache import quickcache
from dimagi.ext.jsonobject import JsonObject, DictProperty


class LocationTypeSpec(JsonObject):
    type = TypeProperty('location_type_name')
    location_id_expression = DictProperty(required=True)

    def configure(self, location_id_expression):
        self._location_id_expression = location_id_expression

    def __call__(self, item, context=None):
        doc_id = self._location_id_expression(item, context)
        if not doc_id:
            return None

        assert context.root_doc['domain']
        return self._get_location_type(doc_id, context, context.root_doc['domain'])

    @staticmethod
    @quickcache(['location_id', 'domain'], timeout=600)
    def _get_location_type(location_id, context, domain):
        sql_location = SQLLocation.objects.filter(
            domain=context.root_doc['domain'],
            location_id=location_id
        )
        if sql_location:
            return sql_location[0].location_type.name
        else:
            return None


def location_type_name(spec, context):
    wrapped = LocationTypeSpec.wrap(spec)
    wrapped.configure(
        location_id_expression=ExpressionFactory.from_spec(wrapped.location_id_expression)
    )
    return wrapped
