from jsonobject import DefaultProperty

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
        location_id_expression=ExpressionFactory.from_spec(wrapped.location_id_expression, context)
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
    return ExpressionFactory.from_spec(spec, context)


class AncestorLocationExpression(JsonObject):
    """
    For a given location id and location type, this expression returns the ancestor of the location that is the
    given type.
    If no such location exists, return None.
    e.g. (boston.location_id, "state") => massachusetts.to_json()
    """
    type = TypeProperty("ancestor_location")
    location_id = DefaultProperty(required=True)
    location_type = DefaultProperty(required=True)

    def configure(self, location_id_expression, location_type_expression):
        self._location_id_expression = location_id_expression
        self._location_type_expression = location_type_expression

    def __call__(self, item, context=None):
        location_id = self._location_id_expression(item, context)
        location_type = self._location_type_expression(item, context)

        cache_key = (self.__class__.__name__, location_id, location_type)
        if context.get_cache_value(cache_key, False) is not False:
            return context.get_cache_value(cache_key)
        ancestor_json = self._get_ancestor(location_id, location_type)
        context.set_cache_value(cache_key, ancestor_json)
        return ancestor_json

    def _get_ancestor(self, location_id, location_type):
        try:
            location = SQLLocation.objects.get(location_id=location_id)
            ancestor = location.get_ancestors(include_self=False).get(location_type__name=location_type)
            return ancestor.to_json()
        except (AttributeError, SQLLocation.DoesNotExist):
            # location is None, or location does not have an ancestor of that type
            return None


def ancestor_location(spec, context):
    wrapped = AncestorLocationExpression.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.location_id, context),
        ExpressionFactory.from_spec(wrapped.location_type, context),
    )
    return wrapped
