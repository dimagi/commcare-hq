from __future__ import absolute_import
from __future__ import unicode_literals
from jsonobject import DefaultProperty, StringProperty

from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.decorators import ucr_context_cache
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.specs import TypeProperty
from corehq.util.quickcache import quickcache
from dimagi.ext.jsonobject import JsonObject, DictProperty


@ucr_context_cache(vary_on=('location_id',))
def _get_location(location_id, context):
    try:
        return SQLLocation.objects.select_related('location_type').get(
            domain=context.root_doc['domain'],
            location_id=location_id
        )
    except SQLLocation.DoesNotExist:
        return None


def _get_location_type_name(location_id, context):
    location = _get_location(location_id, context)
    if not location:
        return None

    return location.location_type.name


class LocationTypeSpec(JsonObject):
    type = TypeProperty('location_type_name')
    location_id_expression = DictProperty(required=True)

    def configure(self, location_id_expression):
        self._location_id_expression = location_id_expression

    def __call__(self, item, context=None):
        doc_id = self._location_id_expression(item, context)
        if not doc_id:
            return None

        return _get_location_type_name(doc_id, context)


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
            "type": "property_name",
            "property_name": "parent_location_id",
        }
    }
    return ExpressionFactory.from_spec(spec, context)


class AncestorLocationExpression(JsonObject):
    """
    This is used to return a json object representing the ancestor of the
    given type of the given location. For instance, if we had locations
    configured with a hierarchy like ``country -> state -> county -> city``,
    we could pass the location id of Cambridge and a location type of state
    to this expression to get the Massachusetts location.

    .. code:: json

       {
           "type": "ancestor_location",
           "location_id": {
               "type": "property_name",
               "name": "owner_id"
           },
           "location_type": {
               "type": "constant",
               "constant": "state"
           }
       }

    If no such location exists, returns null.

    Optionally you can specifiy ``location_property`` to return a single property
    of the location.

    .. code:: json

       {
           "type": "ancestor_location",
           "location_id": {
               "type": "property_name",
               "name": "owner_id"
           },
           "location_type": {
               "type": "constant",
               "constant": "state"
           },
           "location_property": "site_code"
       }
    """
    type = TypeProperty("ancestor_location")
    location_id = DefaultProperty(required=True)
    location_type = DefaultProperty(required=True)
    location_property = StringProperty(required=False)

    def configure(self, location_id_expression, location_type_expression):
        self._location_id_expression = location_id_expression
        self._location_type_expression = location_type_expression

    def __call__(self, item, context=None):
        location_id = self._location_id_expression(item, context)
        location_type = self._location_type_expression(item, context)
        location = self._get_ancestors_by_type(location_id, context).get(location_type)
        if not location:
            return None

        if self.location_property:
            return location.get(self.location_property)

        return location

    @staticmethod
    @ucr_context_cache(vary_on=('location_id',))
    def _get_ancestors_by_type(location_id, context):
        location = _get_location(location_id, context)
        if not location:
            return {}
        ancestors = (location.get_ancestors(include_self=False)
                             .prefetch_related('location_type', 'parent'))
        return {
            ancestor.location_type.name: ancestor.to_json(include_lineage=False)
            for ancestor in ancestors
        }


def ancestor_location(spec, context):
    wrapped = AncestorLocationExpression.wrap(spec)
    wrapped.configure(
        ExpressionFactory.from_spec(wrapped.location_id, context),
        ExpressionFactory.from_spec(wrapped.location_type, context),
    )
    return wrapped
