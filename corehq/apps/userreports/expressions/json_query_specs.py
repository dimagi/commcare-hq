import itertools
from dimagi.ext.jsonobject import JsonObject, DictProperty, StringProperty
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.specs import TypeProperty
from jsonobject.base_properties import DefaultProperty
from .utils import SUPPORTED_UCR_AGGREGATIONS, aggregate_items


class FilterItemsExpressionSpec(JsonObject):
    type = TypeProperty('filter_items')
    items_expression = DefaultProperty(required=True)
    filter_expression = DictProperty(required=True)

    def configure(self, items_expression, filter_expression):
        self._items_expression = items_expression
        self._filter_expression = filter_expression

    def __call__(self, doc, context=None):
        items = self._items_expression(doc, context) or []

        values = []
        for item in items:
            if self._filter_expression(item, context):
                values.append(item)

        return values


class MapItemsExpressionSpec(JsonObject):
    type = TypeProperty('map_items')
    items_expression = DefaultProperty(required=True)
    map_expression = DictProperty(required=True)

    def configure(self, items_expression, map_expression):
        self._items_expression = items_expression
        self._map_expression = map_expression

    def __call__(self, doc, context=None):
        items = self._items_expression(doc, context) or []

        return map(
            lambda i: self._map_expression(i, context),
            items
        )


class ReduceItemsExpressionSpec(JsonObject):
    type = TypeProperty('reduce_items')
    items_expression = DefaultProperty(required=True)
    aggregation_fn = StringProperty(required=True)

    def configure(self, items_expression):
        self._items_expression = items_expression
        if self.aggregation_fn not in SUPPORTED_UCR_AGGREGATIONS:
            raise BadSpecError("aggregation_fn '' is not valid. Valid options are: ".format(
                self.aggregation_fn,
                SUPPORTED_UCR_AGGREGATIONS
            ))

    def __call__(self, doc, context=None):
        items = self._items_expression(doc, context) or []
        return aggregate_items(items, self.aggregation_fn)


class FlattenExpressionSpec(JsonObject):
    type = TypeProperty('flatten')
    items_expression = DefaultProperty(required=True)

    def configure(self, items_expression):
        self._items_expression = items_expression

    def __call__(self, doc, context=None):
        items = self._items_expression(doc, context) or []
        try:
            return(list(itertools.chain(*items)))
        except TypeError:
            return []


class SortItemsExpressionSpec(JsonObject):
    type = TypeProperty('sort_items')
    items_expression = DefaultProperty(required=True)
    sort_expression = DictProperty(required=True)

    def configure(self, items_expression, sort_expression):
        self._items_expression = items_expression
        self._sort_expression = sort_expression

    def __call__(self, doc, context=None):
        items = self._items_expression(doc, context) or []

        return sorted(
            items,
            key=lambda i: self._sort_expression(i, context),
        )
