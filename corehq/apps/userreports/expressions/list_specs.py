from __future__ import absolute_import
from __future__ import unicode_literals
import itertools
from django.utils.translation import ugettext as _

from corehq.apps.userreports.mixins import NoPropertyTypeCoercionMixIn
from dimagi.ext.jsonobject import JsonObject, DictProperty, StringProperty
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.specs import TypeProperty
from corehq.apps.userreports.util import add_tabbed_text
from jsonobject.base_properties import DefaultProperty
from .utils import SUPPORTED_UCR_AGGREGATIONS, aggregate_items


def _evaluate_items_expression(itemx_ex, doc, context):
    result = itemx_ex(doc, context)
    if not isinstance(result, list):
        return []
    else:
        return result


class FilterItemsExpressionSpec(NoPropertyTypeCoercionMixIn, JsonObject):
    """
    ``filter_items`` performs filtering on given list and returns a new
    list. If the boolean expression specified by ``filter_expression``
    evaluates to a ``True`` value, the item is included in the new list and
    if not, is not included in the new list.

    ``items_expression`` can be any valid expression that returns a list. If
    this doesn't evaluate to a list an empty list is returned. It may be
    necessary to specify a ``datatype`` of ``array`` if the expression could
    return a single element.

    ``filter_expression`` can be any valid boolean expression relative to
    the items in above list.

    .. code:: json

       {
           "type": "filter_items",
           "items_expression": {
               "datatype": "array",
               "type": "property_name",
               "property_name": "family_repeat"
           },
           "filter_expression": {
              "type": "boolean_expression",
               "expression": {
                   "type": "property_name",
                   "property_name": "gender"
               },
               "operator": "eq",
               "property_value": "female"
           }
       }
    """
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

    def __str__(self):
        return "filter:\n{items}\non:\n{filter}\n".format(items=add_tabbed_text(str(self._items_expression)),
                                                          filter=add_tabbed_text(str(self._filter_expression)))


class MapItemsExpressionSpec(NoPropertyTypeCoercionMixIn, JsonObject):
    """
    ``map_items`` performs a calculation specified by ``map_expression`` on
    each item of the list specified by ``items_expression`` and returns a
    list of the calculation results. The ``map_expression`` is evaluated
    relative to each item in the list and not relative to the parent
    document from which the list is specified. For e.g. if
    ``items_expression`` is a path to repeat-list of children in a form
    document, ``map_expression`` is a path relative to the repeat item.

    ``items_expression`` can be any valid expression that returns a list. If
    this doesn't evaluate to a list an empty list is returned. It may be
    necessary to specify a ``datatype`` of ``array`` if the expression could
    return a single element.

    ``map_expression`` can be any valid expression relative to the items in
    above list.

    .. code:: json

       {
           "type": "map_items",
           "items_expression": {
               "datatype": "array",
               "type": "property_path",
               "property_path": ["form", "child_repeat"]
           },
           "map_expression": {
               "type": "property_path",
               "property_path": ["age"]
           }
       }

    Above returns list of ages. Note that the ``property_path`` in
    ``map_expression`` is relative to the repeat item rather than to the
    form.
    """
    type = TypeProperty('map_items')
    items_expression = DefaultProperty(required=True)
    map_expression = DefaultProperty(required=True)

    def configure(self, items_expression, map_expression):
        self._items_expression = items_expression
        self._map_expression = map_expression

    def __call__(self, doc, context=None):
        items = _evaluate_items_expression(self._items_expression, doc, context)

        return [self._map_expression(i, context) for i in items]

    def __str__(self):
        return "map:\n{items}\nto:\n{map}\n".format(items=add_tabbed_text(str(self._items_expression)),
                                                    map=add_tabbed_text(str(self._map_expression)))


class ReduceItemsExpressionSpec(NoPropertyTypeCoercionMixIn, JsonObject):
    """
    ``reduce_items`` returns aggregate value of the list specified by
    ``aggregation_fn``.

    ``items_expression`` can be any valid expression that returns a list. If
    this doesn't evaluate to a list, ``aggregation_fn`` will be applied on
    an empty list. It may be necessary to specify a ``datatype`` of
    ``array`` if the expression could return a single element.

    ``aggregation_fn`` is one of following supported functions names.

    +----------------+-----------------------+
    | Function Name  | Example               |
    +================+=======================+
    | ``count``      | ``['a', 'b']`` -> 2   |
    +----------------+-----------------------+
    | ``sum``        | ``[1, 2, 4]`` -> 7    |
    +----------------+-----------------------+
    | ``min``        | ``[2, 5, 1]`` -> 1    |
    +----------------+-----------------------+
    | ``max``        | ``[2, 5, 1]`` -> 5    |
    +----------------+-----------------------+
    | ``first_item`` | ``['a', 'b']`` -> 'a' |
    +----------------+-----------------------+
    | ``last_item``  | ``['a', 'b']`` -> 'b' |
    +----------------+-----------------------+

    .. code:: json

       {
           "type": "reduce_items",
           "items_expression": {
               "datatype": "array",
               "type": "property_name",
               "property_name": "family_repeat"
           },
           "aggregation_fn": "count"
       }

    This returns number of family members
    """
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

    def __str__(self):
        return "{aggregation}:\n{items}\n".format(aggregation=self.aggregation_fn,
                                                  items=add_tabbed_text(str(self._items_expression)))


class FlattenExpressionSpec(NoPropertyTypeCoercionMixIn, JsonObject):
    """
    ``flatten`` takes list of list of objects specified by
    ``items_expression`` and returns one list of all objects.

    ``items_expression`` is any valid expression that returns a list of
    lists. It this doesn't evaluate to a list of lists an empty list is
    returned. It may be necessary to specify a ``datatype`` of ``array`` if
    the expression could return a single element.

    .. code:: json

       {
           "type": "flatten",
           "items_expression": {},
   }
    """
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

    def __str__(self):
        return "flatten:\n{items}\n".format(items=add_tabbed_text(str(self._items_expression)))


class SortItemsExpressionSpec(NoPropertyTypeCoercionMixIn, JsonObject):
    """
    ``sort_items`` returns a sorted list of items based on sort value of
    each item.The sort value of an item is specified by ``sort_expression``.
    By default, list will be in ascending order. Order can be changed by
    adding optional ``order`` expression with one of ``DESC`` (for
    descending) or ``ASC`` (for ascending) If a sort-value of an item is
    ``None``, the item will appear in the start of list. If sort-values of
    any two items can't be compared, an empty list is returned.

    ``items_expression`` can be any valid expression that returns a list. If
    this doesn't evaluate to a list an empty list is returned. It may be
    necessary to specify a ``datatype`` of ``array`` if the expression could
    return a single element.

    ``sort_expression`` can be any valid expression relative to the items in
    above list, that returns a value to be used as sort value.

    .. code:: json

       {
           "type": "sort_items",
           "items_expression": {
               "datatype": "array",
               "type": "property_path",
               "property_path": ["form", "child_repeat"]
           },
           "sort_expression": {
               "type": "property_path",
               "property_path": ["age"]
           }
       }
    """
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
            def sort_key(item):
                value = self._sort_expression(item, context)
                # swap 0 and 1 to sort nulls last instead of first
                return (0 if value is None else 1), value

            return sorted(
                items,
                key=sort_key,
                reverse=True if self.order == self.DESC else False
            )
        except TypeError:
            return []

    def __str__(self):
        return "sort:\n{items}\n{order} on:\n{sort}".format(
            items=add_tabbed_text(str(self._items_expression)),
            order=self.order,
            sort=add_tabbed_text(str(self._sort_expression)))
