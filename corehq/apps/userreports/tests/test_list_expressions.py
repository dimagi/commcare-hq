import datetime
from copy import copy

from django.test import SimpleTestCase

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.expressions.utils import COUNT
from corehq.util.test_utils import generate_cases


_filter_v1 = {
    'type': 'boolean_expression',
    'operator': 'eq',
    'expression': {
        'type': 'property_name',
        'property_name': 'key',
    },
    'property_value': 'v1',
}


@generate_cases([
    ([{'key': 'v1'}, {'key': 'v2'}], None),
    ([{'key': 'v1'}, {'key': 'v2'}], {}),
    (None, _filter_v1),
    ({}, _filter_v1),
    # non-boolean expressions are invalid
    ([{'key': 'v1'}, {'key': 'v2'}], {'type': 'identity'}),
])
def test_filter_items_bad_spec(self, items_ex, filter_ex):
    expression = {
        'type': 'filter_items',
    }
    if items_ex is not None:
        expression['items_expression'] = items_ex
    if filter_ex is not None:
        expression['filter_expression'] = filter_ex

    with self.assertRaises(BadSpecError):
        ExpressionFactory.from_spec(expression)


@generate_cases([
    (
        {'items': [{'key': 'v1'}, {'key': 'v2'}]},
        {'type': 'property_name', 'property_name': 'items'},
        _filter_v1,
        [{'key': 'v1'}]
    ),
    (
        [{'key': 'v1'}, {'key': 'v2'}],
        {'type': 'identity'},
        _filter_v1,
        [{'key': 'v1'}]
    ),
    # literal
    (
        [],
        [{'key': 'v1'}, {'key': 'v2'}],
        _filter_v1,
        [{'key': 'v1'}]
    ),
    # if items_expression doesn't match empty list is returned
    (
        {'items': [{'key': 'v1'}, {'key': 'v2'}]},
        {'type': 'property_name', 'property_name': 'wrong_prop'},
        _filter_v1,
        []
    ),
    # if filter doesn't match, empty list is returned
    (
        {'items': [{'key': 'v1'}, {'key': 'v2'}]},
        {'type': 'property_name', 'property_name': 'items'},
        {
            'type': 'boolean_expression',
            'operator': 'eq',
            'expression': {
                'type': 'property_name',
                'property_name': 'key',
            },
            'property_value': 'no_match',
        },
        []
    ),
    # if items_expression returns non-iterable return empty list
    (
        34,
        {'type': 'identity'},
        _filter_v1,
        []
    ),
])
def test_filter_items_basic(self, doc, items_ex, filter_ex, expected):
    expression = ExpressionFactory.from_spec({
        'type': 'filter_items',
        'items_expression': items_ex,
        'filter_expression': filter_ex
    })
    self.assertEqual(expression(doc), expected)


@generate_cases([
    ([{'key': 'v1'}, {'key': 'v2'}], None),
    ([{'key': 'v1'}, {'key': 'v2'}], {}),
    (None, {'type': 'identity'}),
    ({}, {'type': 'identity'}),
])
def test_map_items_bad_spec(self, items_ex, map_ex):
    expression = {
        'type': 'map_items',
    }
    if items_ex is not None:
        expression['items_expression'] = items_ex
    if map_ex is not None:
        expression['map_expression'] = map_ex

    with self.assertRaises(BadSpecError):
        ExpressionFactory.from_spec(expression)(items_ex, map_ex)


@generate_cases([
    (
        {'items': [{'key': 'v1'}, {'key': 'v2'}]},
        {'type': 'property_name', 'property_name': 'items'},
        {'type': 'property_name', 'property_name': 'key'},
        ['v1', 'v2']
    ),
    (
        [{'key': 'v1'}, {'key': 'v2'}],
        {'type': 'identity'},
        {'type': 'property_name', 'property_name': 'key'},
        ['v1', 'v2']
    ),
    (
        {'items': [{'key': 'v1'}, {'key': 'v2'}]},
        {'type': 'property_name', 'property_name': 'items'},
        {'type': 'identity'},
        [{'key': 'v1'}, {'key': 'v2'}],
    ),
    # literal
    (
        [],
        [{'key': 'v1'}, {'key': 'v2'}],
        {'type': 'identity'},
        [{'key': 'v1'}, {'key': 'v2'}],
    ),
    # map_expression can return empty on an item
    (
        {'items': [{'key': 'v1'}, {'no_key': 'v2'}]},
        {'type': 'property_name', 'property_name': 'items'},
        {'type': 'property_name', 'property_name': 'key'},
        ['v1', None]
    ),
    # if items_expression returns empty, an empty list is returned
    (
        {'items': [{'key': 'v1'}, {'no_key': 'v2'}]},
        {'type': 'property_name', 'property_name': 'no_match'},
        {'type': 'property_name', 'property_name': 'key'},
        []
    ),
    # if items_expression returns non-iterable return empty list
    (
        34,
        {'type': 'identity'},
        {'type': 'identity'},
        []
    ),
])
def test_map_items_basic(self, doc, items_ex, map_ex, expected):
    expression = ExpressionFactory.from_spec({
        'type': 'map_items',
        'items_expression': items_ex,
        'map_expression': map_ex
    })
    self.assertEqual(expression(doc), expected)


@generate_cases([
    ([{'key': 'v1'}, {'key': 'v2'}], None),
    ({'type': 'identity'}, {}),
    ({'type': 'identity'}, 'invalid_agg_fn'),
])
def test_reduce_items_bad_spec(self, items_ex, reduce_ex):
    expression = {
        'type': 'reduce_items',
    }
    if items_ex is not None:
        expression['items_expression'] = items_ex
    if reduce_ex is not None:
        expression['aggregation_fn'] = reduce_ex

    with self.assertRaises(BadSpecError):
        ExpressionFactory.from_spec(expression)(items_ex, reduce_ex)


@generate_cases([
    (
        ['a', 'b'],
        {'type': 'identity'},
        'count',
        2,
    ),
    (
        {'items': ['a', 'b']},
        {'type': 'property_name', 'property_name': 'items'},
        'count',
        2,
    ),
    (
        {'items': ['a', 'b']},
        {'type': 'property_name', 'property_name': 'no_match'},
        'count',
        0,
    ),
    (
        [1, 2],
        {'type': 'identity'},
        'sum',
        3
    ),
    (
        [1, 2],
        {'type': 'identity'},
        'min',
        1
    ),
    (
        [1, 2],
        {'type': 'identity'},
        'max',
        2
    ),
    (
        [1, 2],
        {'type': 'identity'},
        'first_item',
        1
    ),
    (
        [1, 2],
        {'type': 'identity'},
        'last_item',
        2
    ),
    # if items can't be compared should return None
    (
        [datetime.datetime.now(), datetime.date.today()],
        {'type': 'identity'},
        'max',
        None,
    ),
    # if items_expression returns non-iterable reduce(count) should return 0
    (
        34,
        {'type': 'identity'},
        'count',
        0
    ),
    # if items_expression returns non-iterable reduce(sum) should return 0
    (
        34,
        {'type': 'identity'},
        'sum',
        0
    ),
    # if items_expression returns non-iterable reduce(count) should return None
    (
        34,
        {'type': 'identity'},
        'last_item',
        None
    ),
    # if items_expression returns non-iterable reduce(count) should return None
    (
        34,
        {'type': 'identity'},
        'first_item',
        None
    ),
    # if items_expression returns [] reduce(count) should return 0
    (
        [],
        {'type': 'identity'},
        'count',
        0
    ),
    # if items_expression returns [] reduce(sum) should return 0
    (
        [],
        {'type': 'identity'},
        'sum',
        0
    ),
    # if items_expression returns [] reduce(count) should return None
    (
        [],
        {'type': 'identity'},
        'last_item',
        None
    ),
    # if items_expression returns [] reduce(count) should return None
    (
        [],
        {'type': 'identity'},
        'first_item',
        None
    ),

])
def test_reduce_items_basic(self, doc, items_ex, reduce_ex, expected):
    expression = ExpressionFactory.from_spec({
        'type': 'reduce_items',
        'items_expression': items_ex,
        'aggregation_fn': reduce_ex
    })
    self.assertEqual(expression(doc), expected)


@generate_cases([
    ({}, ), (None, )
])
def test_flatten_bad_spec(self, items_ex):
    with self.assertRaises(BadSpecError):
        ExpressionFactory.from_spec({
            'type': 'flatten',
            'items_expression': items_ex
        })


@generate_cases([
    (
        {'k': [[1, 2], [4, 5]]},
        {'type': 'property_name', 'property_name': 'k'},
        [1, 2, 4, 5]
    ),
    (
        {},
        [[1, 2], [4, 5]],
        [1, 2, 4, 5]
    ),
    (
        [[1, 2], [4, 5]],
        {'type': 'identity'},
        [1, 2, 4, 5]
    ),
    (
        [[1, 2], 4, 5],
        {'type': 'identity'},
        []
    ),
    # if an iterm in the list is not a list, return empty
    (
        ["a", "b"],
        {'type': 'identity'},
        [],
    ),
    # if an iterm in the list is not a list, return empty
    (
        [1, 2],
        {'type': 'identity'},
        [],
    ),
    # if items_expression returns non-iterable return empty list
    (
        34,
        {'type': 'identity'},
        []
    ),
])
def test_flatten_basic(self, doc, items_ex, expected):
    expression = ExpressionFactory.from_spec({
        'type': 'flatten',
        'items_expression': items_ex
    })
    self.assertEqual(expression(doc), expected)


@generate_cases([
    ([{'key': 'v1'}, {'key': 'v2'}], None),
    ([{'key': 'v1'}, {'key': 'v2'}], {}),
    (None, {'type': 'identity'}),
    ({}, {'type': 'identity'}),
])
def test_sort_items_bad_spec(self, items_ex, sort_ex):
    expression = {
        'type': 'sort_items',
    }
    if items_ex is not None:
        expression['items_expression'] = items_ex
    if sort_ex is not None:
        expression['sort_expression'] = sort_ex

    with self.assertRaises(BadSpecError):
        ExpressionFactory.from_spec(expression)(items_ex, sort_ex)


class TestSortOrderExpression(SimpleTestCase):

    def test_bad_order_raises_badspec(self):
        expression = {
            'type': 'sort_items',
            'items_expression': [1, 6, 2, 3],
            'sort_expression': {'type': 'identity'},
            'order': 'complex'
        }
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec(expression)

    def test_descending_order(self):
        expression = {
            'type': 'sort_items',
            'items_expression': [1, 6, 2, 3],
            'sort_expression': {'type': 'identity'},
            'order': 'DESC'
        }
        self.assertEqual(ExpressionFactory.from_spec(expression)({}), [6, 3, 2, 1])


@generate_cases([
    (
        {'items': [{'key': 2}, {'key': 1}]},
        {'type': 'property_name', 'property_name': 'items'},
        {'type': 'property_name', 'property_name': 'key'},
        [{'key': 1}, {'key': 2}],
    ),
    (
        [{'key': 2}, {'key': 1}],
        {'type': 'identity'},
        {'type': 'property_name', 'property_name': 'key'},
        [{'key': 1}, {'key': 2}],
    ),
    (
        {'items': [2, 1, 3]},
        {'type': 'property_name', 'property_name': 'items'},
        {'type': 'identity'},
        [1, 2, 3],
    ),
    (
        [2, 1, 3],
        {'type': 'identity'},
        {'type': 'identity'},
        [1, 2, 3],
    ),
    # any possible python object comparison is supported
    (
        [datetime.date(2013, 1, 2), datetime.date(2013, 1, 1), datetime.date(2013, 1, 3)],
        {'type': 'identity'},
        {'type': 'identity'},
        [datetime.date(2013, 1, 1), datetime.date(2013, 1, 2), datetime.date(2013, 1, 3)],
    ),
    # if sort_by returns empty, items are left in the same order
    (
        {'items': [{'key': 2}, {'key': 1}]},
        {'type': 'property_name', 'property_name': 'items'},
        {'type': 'property_name', 'property_name': 'no_match'},
        [{'key': 2}, {'key': 1}],  # no sort
    ),
    # if sort_by returns empty for an item, it's inserted at the beginning of list
    (
        {'items': [{'key': 2}, {'no_key_match': 3}, {'key': 1}]},
        {'type': 'property_name', 'property_name': 'items'},
        {'type': 'property_name', 'property_name': 'key'},
        [{'no_key_match': 3}, {'key': 1}, {'key': 2}],   # no sort
    ),
    # if items_expression doesn't match, empty list is returned
    (
        {'items': [{'key': 2}, {'key': 1}]},
        {'type': 'property_name', 'property_name': 'no_match'},
        {'type': 'property_name', 'property_name': 'key'},
        [],
    ),
    # if sort values of two items can't be compared, empty list is returned
    (
        [datetime.date(2013, 1, 2), 1, datetime.date(2013, 1, 3)],
        {'type': 'identity'},
        {'type': 'identity'},
        []
    ),
])
def test_sort_items_basic(self, doc, items_ex, sort_ex, expected):
    expression = ExpressionFactory.from_spec({
        'type': 'sort_items',
        'items_expression': items_ex,
        'sort_expression': sort_ex
    })
    self.assertEqual(expression(doc), expected)


class NestedExpressionTest(SimpleTestCase):
    DATE = datetime.date(2018, 1, 1)
    DATE_LITERAL = '2018-01-01'
    DATE_CONSTANT_EXPRESSION = {
        'type': 'constant',
        'constant': '2018-01-01',
        'datatype': 'date',
    }
    DATE_LITERAL_FILTER = {
        'type': 'boolean_expression',
        'operator': 'eq',
        'expression': {
            'type': 'identity',
        },
        'property_value': DATE_LITERAL,
    }
    DATE_CONSTANT_FILTER = {
        'type': 'boolean_expression',
        'operator': 'eq',
        'expression': {
            'type': 'identity',
        },
        'property_value': DATE_CONSTANT_EXPRESSION,
    }
    ITEMS_EXPRESSION = {
        'type': 'iterator',
        "expressions": [
            DATE_LITERAL,
            DATE_CONSTANT_EXPRESSION,
            'not a date',
        ],
    }

    def test_filter_items_with_nested_dates(self):
        for filter_spec in [self.DATE_LITERAL_FILTER, self.DATE_CONSTANT_FILTER]:
            expression = ExpressionFactory.from_spec({
                "type": "filter_items",
                "items_expression": self.ITEMS_EXPRESSION,
                "filter_expression": filter_spec,
            })
            self.assertEqual(2, len(expression({})))

    def test_map_items_with_nested_dates(self):
        for inner_expression_spec in [self.DATE_LITERAL, self.DATE_CONSTANT_EXPRESSION]:
            expression = ExpressionFactory.from_spec({
                "type": "map_items",
                "items_expression": self.ITEMS_EXPRESSION,
                "map_expression": inner_expression_spec,
            })
            result = expression({})
            self.assertEqual(3, len(result))
            for val in result:
                self.assertEqual(self.DATE, val)

    def test_reduce_items_with_nested_dates(self):
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "items_expression": self.ITEMS_EXPRESSION,
            "aggregation_fn": COUNT,
        })
        self.assertEqual(3, expression({}))

    def test_flatten_items_with_nested_dates(self):
        expression = ExpressionFactory.from_spec({
            "type": "flatten",
            "items_expression": self.ITEMS_EXPRESSION,
        })
        # in this case the expression fails and defaults to an empty list because the inner dates aren't iterable
        # this is fine as the bug was actually in the generation of the expression from the factory
        self.assertEqual([], expression({}))

    def test_sort_items_with_nested_dates(self):
        items_expression = copy(self.ITEMS_EXPRESSION)
        items_expression['expressions'] = items_expression['expressions'][:2]
        expression = ExpressionFactory.from_spec({
            "type": "sort_items",
            "items_expression": items_expression,
            "sort_expression": {'type': 'identity'}
        })
        result = expression({})
        self.assertEqual(2, len(result))
        for val in result:
            self.assertEqual(self.DATE, val)


class ListExpressionTest(SimpleTestCase):
    """
    Test filter, map, reduce, sort and flatten together for few expected use cases
    """

    def test_latest_property(self):
        doc = {
            "forms": [
                {"received_on": datetime.date(2015, 4, 5), "weight": 21},
                {"received_on": datetime.date(2015, 1, 5), "weight": 18},
                {"received_on": datetime.date(2015, 3, 5), "weight": 20},
            ]
        }
        # nested(weight) <- reduce(last_item) <- sort(by received_on) <- forms
        expression = ExpressionFactory.from_spec({
            "type": "nested",
            "argument_expression": {
                "type": "reduce_items",
                "items_expression": {
                    "type": "sort_items",
                    "items_expression": {"type": "property_name", "property_name": "forms"},
                    "sort_expression": {"type": "property_name", "property_name": "received_on"}
                },
                "aggregation_fn": "last_item"
            },
            "value_expression": {
                "type": "property_name",
                "property_name": "weight"
            }
        })
        self.assertEqual(expression(doc), doc["forms"][0]["weight"])

    def test_repeat_calculation(self):
        _rations1, _rations2, _rations3 = 3, 4, 5
        doc = {
            "forms": [
                {"id": "f1", "child_repeat": [
                    {"name": "a", "rations": _rations1}, {"name": "b", "rations": 3}, {"name": "c", "rations": 3}
                ]},
                {"id": "f2", "child_repeat": [
                    {"name": "c", "rations": 3}, {"name": "a", "rations": _rations2}, {"name": "b", "rations": 3}
                ]},
                {"id": "f3", "child_repeat": [
                    {"name": "a", "rations": _rations3}, {"name": "b", "rations": 3}, {"name": "c", "rations": 3}
                ]},
            ]
        }
        #  reduce(to sum ) <- map(weight) <- filter(by name) <- flatten(child_repeat) <- map(child_repeat) <- forms
        expression = ExpressionFactory.from_spec({
            "type": "reduce_items",
            "items_expression": {
                "type": "map_items",
                "items_expression": {
                    "type": "filter_items",
                    "items_expression": {
                        "type": "flatten",
                        "items_expression": {
                            "type": "map_items",
                            "items_expression": {
                                "type": "property_name",
                                "property_name": "forms"
                            },
                            "map_expression": {
                                "type": "property_name",
                                "property_name": "child_repeat"
                            }
                        }
                    },
                    "filter_expression": {
                        "type": "boolean_expression",
                        "operator": "eq",
                        "expression": {"type": "property_name", "property_name": "name"},
                        "property_value": "a"
                    }
                },
                "map_expression": {
                    "type": "property_name",
                    "property_name": "rations"
                }
            },
            "aggregation_fn": "sum"
        })
        self.assertEqual(expression(doc), _rations1 + _rations2 + _rations3)
