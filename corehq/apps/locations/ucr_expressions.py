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
        return self._get_location_type(doc_id, context.root_doc['domain'])

    @staticmethod
    @quickcache(['location_id', 'domain'], timeout=600)
    def _get_location_type(location_id, domain):
        sql_location = SQLLocation.objects.filter(
            domain=domain,
            location_id=location_id
        )
        if sql_location:
            return sql_location[0].location_type.name
        else:
            return None


class LocationParentIdSpec(JsonObject):
    type = TypeProperty('location_parent_id')
    location_id_expression = DictProperty(required=True)


def location_type_name(spec, context):
    wrapped = LocationTypeSpec.wrap(spec)
    wrapped.configure(
        location_id_expression=ExpressionFactory.from_spec(wrapped.location_id_expression)
    )
    return wrapped


def location_parent_id(spec, context):
    LocationParentIdSpec.wrap(spec)  # this is just for validation
    spec = {
        "type": "related_doc",
        "related_doc_type": "Location",
        "doc_id_expression": spec['location_id_expression'],
        "value_expression": {
            "type": "array_index",
            'array_expression': {
                'type': 'property_name',
                'property_name': 'lineage'
            },
            'index_expression': 0,
        }
    }
    return ExpressionFactory.from_spec(spec)
