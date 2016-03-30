import itertools
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from django.test import SimpleTestCase


class FilterItemsExpressionTest(SimpleTestCase):

    def _make_expression(self, items_expression=None, filter_expression=None):
        expression = {
            'type': 'filter_items',
        }
        if items_expression is not None:
            expression['items_expression'] = items_expression

        if filter_expression is not None:
            expression['filter_expression'] = filter_expression

        return ExpressionFactory.from_spec(expression)

    @classmethod
    def setUpClass(cls):
        cls.gmp_forms = [
            {'type': 'gmp', 'form_id': 'gmp_form_1', 'weight': 1},
            {'type': 'gmp', 'form_id': 'gmp_form_2', 'weight': 2},
            {'type': 'gmp', 'form_id': 'gmp_form_3', 'weight': 3},
        ]
        cls.thr_forms = [
            {'type': 'thr', 'form_id': 'thr_form_1', 'num_thr': 1},
        ]
        cls.case_doc = {
            'forms': cls.gmp_forms + cls.thr_forms
        }

    def setUp(self):
        self.filter_expression = {
            'type': 'boolean_expression',
            'operator': 'eq',
            'expression': {
                'type': 'property_name',
                'property_name': 'type',
            },
            'property_value': 'gmp',
        }
        self.items_expression = {
            'type': 'property_name',
            'property_name': 'forms'
        }

    def test_empty_expressions(self):
        expressions = [
            (self.items_expression, None),
            (None, self.filter_expression),
            (self.items_expression, {}),
            ({}, self.filter_expression)
        ]
        for expression in expressions:
            with self.assertRaises(BadSpecError):
                self._make_expression(*expression)

    def test_basic(self):
        expression = self._make_expression(self.items_expression, self.filter_expression)
        self.assertEqual(expression(self.case_doc), self.gmp_forms)

    def test_no_filter_match(self):
        self.filter_expression['property_value'] = 'unknown_type'
        expression = self._make_expression(self.items_expression, self.filter_expression)
        self.assertEqual(expression(self.case_doc), [])


class MapItemsExpressionTest(SimpleTestCase):
    # todo - more test coverage
    def test_basic(self):
        doc = {
            'items': [
                {'a': 1, 'b': 'b1'},
                {'a': 2, 'b': 'b2'},
                {'a': 3, 'b': 'b3'},
            ]
        }
        expression = ExpressionFactory.from_spec({
            'type': 'map_items',
            'items_expression': {
                'type': 'property_name',
                'property_name': 'items'
            },
            'map_expression': {
                'type': 'property_name',
                'property_name': 'a'
            }
        })
        self.assertEqual(expression(doc), map(lambda x: x['a'], doc['items']))


class ReduceItemsExpressionTest(SimpleTestCase):
    # todo - more test coverage
    def test_basic(self):
        doc = {
            'items': [
                {'a': 1, 'b': 'b1'},
                {'a': 2, 'b': 'b2'},
                {'a': 3, 'b': 'b3'},
            ]
        }
        expression = ExpressionFactory.from_spec({
            'type': 'reduce_items',
            'items_expression': {
                'type': 'property_name',
                'property_name': 'items'
            },
            'aggregation_fn': 'count'
        })
        self.assertEqual(expression(doc), len(doc['items']))


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
