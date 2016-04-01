import itertools
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.util.test_utils import generate_cases
from django.test import SimpleTestCase


def _make_filter_expression(items_expression=None, filter_expression=None):
    expression = {
        'type': 'filter_items',
    }
    if items_expression is not None:
        expression['items_expression'] = items_expression

    if filter_expression is not None:
        expression['filter_expression'] = filter_expression

    return ExpressionFactory.from_spec(expression)


def _make_map_expression(items_expression=None, map_expression=None):
    expression = {
        'type': 'map_items',
    }
    if items_expression is not None:
        expression['items_expression'] = items_expression

    if map_expression is not None:
        expression['map_expression'] = map_expression

    return ExpressionFactory.from_spec(expression)


def _make_reduce_expression(items_expression=None, agg_fn=None):
    expression = {
        'type': 'reduce_items',
    }
    if items_expression is not None:
        expression['items_expression'] = items_expression

    if agg_fn is not None:
        expression['aggregation_fn'] = agg_fn

    return ExpressionFactory.from_spec(expression)

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
    ([], _filter_v1),
])
def test_filter_items_bad_spec(self, items_ex, filter_ex):
    with self.assertRaises(BadSpecError):
        _make_filter_expression(items_ex, filter_ex)


@generate_cases([
    (
        [{'key': 'v1'}, {'key': 'v2'}],
        {'type': 'identity'},
        _filter_v1,
        [{'key': 'v1'}]
    ),
    (   # literal
        [],
        [{'key': 'v1'}, {'key': 'v2'}],
        _filter_v1,
        [{'key': 'v1'}]
    ),
    (
        {'items': [{'key': 'v1'}, {'key': 'v2'}]},
        {'type': 'property_name', 'property_name': 'items'},
        _filter_v1,
        [{'key': 'v1'}]
    ),
])
def test_filter_items_basic(self, doc, items_ex, filter_ex, expected):
    expression = _make_filter_expression(items_ex, filter_ex)
    self.assertEqual(expression(doc), expected)


@generate_cases([
    ([{'key': 'v1'}, {'key': 'v2'}], None),
    ([{'key': 'v1'}, {'key': 'v2'}], {}),
    (None, {'type': 'identity'}),
    ({}, {'type': 'identity'}),
    ([], {'type': 'identity'}),
])
def test_map_items_bad_spec(self, items_ex, map_ex):
    with self.assertRaises(BadSpecError):
        _make_map_expression(items_ex, map_ex)


@generate_cases([
    (
        [{'key': 'v1'}, {'key': 'v2'}],
        {'type': 'identity'},
        {'type': 'identity'},
        [{'key': 'v1'}, {'key': 'v2'}],
    ),
    (   # literal
        [],
        [{'key': 'v1'}, {'key': 'v2'}],
        {'type': 'identity'},
        [{'key': 'v1'}, {'key': 'v2'}],
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
        {'type': 'property_name', 'property_name': 'key'},
        ['v1', 'v2']
    ),
])
def test_map_items_basic(self, doc, items_ex, map_ex, expected):
    expression = _make_map_expression(items_ex, map_ex)
    self.assertEqual(expression(doc), expected)


@generate_cases([
    ([{'key': 'v1'}, {'key': 'v2'}], None),
    ({'type': 'identity'}, {}),
    ({'type': 'identity'}, 'invalid_agg_fn'),
])
def test_reduce_items_bad_spec(self, items_ex, reduce_ex):
    with self.assertRaises(BadSpecError):
        _make_reduce_expression(items_ex, reduce_ex)


@generate_cases([
    (
        ['a', 'b']
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
    (   # literal
        [],
        {'type': 'identity'},
        'count',
        0,
    ),
    (
        [1, 2]
        {'type': 'identity'},
        'sum',
        ['v1', 'v2']
    ),
])
def test_reduce_items_basic(self, doc, items_ex, reduce_ex, expected):
    expression = _make_reduce_expression(items_ex, reduce_ex)
    self.assertEqual(expression(doc), expected)


class FlattenExpressionTest(SimpleTestCase):
    # todo - more test coverage
    def test_basic(self):
        doc = {
            'items': [
                [{'repeat': 'repeat11'}, {'repeat': 'repeat12'}],
                [{'repeat': 'repeat21'}],
                [{'repeat': 'repeat31'}, {'repeat': 'repeat32'}],
            ]
        }

        expression = ExpressionFactory.from_spec({
            'type': 'flatten',
            'items_expression': {
                'type': 'property_name',
                'property_name': 'items'
            }
        })
        expected = list(itertools.chain(*doc['items']))
        self.assertEqual(expression(doc), expected)
