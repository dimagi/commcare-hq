import itertools
from django.utils.translation import ugettext as _
from dimagi.ext.jsonobject import JsonObject, DictProperty, StringProperty
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.specs import TypeProperty
from jsonobject.base_properties import DefaultProperty
from .utils import SUPPORTED_UCR_AGGREGATIONS, aggregate_items


def _evaluate_items_expression(itemx_ex, doc, context):
    result = itemx_ex(doc, context)
    if not isinstance(result, list):
        return []
    else:
        return result


class FilterItemsExpressionSpec(JsonObject):
    type = TypeProperty('filter_items')
    items_expression = DefaultProperty(required=True)
    filter_expression = DictProperty(required=True)

    def configure(self, items_expression, filter_expression):
        self._items_expression = items_expression
        self._filter_expression = filter_expression

    def __call__(self, doc, context=None):
        items = _evaluate_items_expression(self._items_expression, doc, context)

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
        items = _evaluate_items_expression(self._items_expression, doc, context)

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
            raise BadSpecError(_("aggregation_fn '{}' is not valid. Valid options are: {} ").format(
                self.aggregation_fn,
                SUPPORTED_UCR_AGGREGATIONS
            ))

    def __call__(self, doc, context=None):
        items = _evaluate_items_expression(self._items_expression, doc, context)
        return aggregate_items(items, self.aggregation_fn)


class FlattenExpressionSpec(JsonObject):
    type = TypeProperty('flatten')
    items_expression = DefaultProperty(required=True)

    def configure(self, items_expression):
        self._items_expression = items_expression

    def __call__(self, doc, context=None):
        items = _evaluate_items_expression(self._items_expression, doc, context)
        #  all items should be iterable, if not return empty list
        for item in items:
            if not isinstance(item, list):
                return []
        try:
            return(list(itertools.chain(*items)))
        except TypeError:
            return []


class SortItemsExpressionSpec(JsonObject):
    ASC, DESC = "ASC", "DESC"
    type = TypeProperty('sort_items')
    items_expression = DefaultProperty(required=True)
    sort_expression = DictProperty(required=True)
    order = StringProperty(choices=[ASC, DESC], default=ASC)

    def configure(self, items_expression, sort_expression):
        self._items_expression = items_expression
        self._sort_expression = sort_expression

    def __call__(self, doc, context=None):
        items = _evaluate_items_expression(self._items_expression, doc, context)

        try:
            return sorted(
                items,
                key=lambda i: self._sort_expression(i, context),
                reverse=True if self.order == self.DESC else False
            )
        except TypeError:
            return []
