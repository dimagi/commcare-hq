import datetime

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
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
        [],
        {'type': 'identity'},
        'count',
        0,
    ),
    (
        [1, 2],
        {'type': 'identity'},
        'sum',
        3
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
    (
        ["a", "b"],
        {'type': 'identity'},
        ["a", "b"],
    ),
    (
        [1, 2],
        {'type': 'identity'},
        [],
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
])
def test_sort_items_basic(self, doc, items_ex, sort_ex, expected):
    expression = ExpressionFactory.from_spec({
        'type': 'sort_items',
        'items_expression': items_ex,
        'sort_expression': sort_ex
    })
    self.assertEqual(expression(doc), expected)
