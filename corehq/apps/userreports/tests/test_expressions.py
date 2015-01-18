from django.test import SimpleTestCase
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.expressions.getters import NestedDictGetter, DictGetter
from corehq.apps.userreports.specs import EvaluationContext


class ConstantExpressionTest(SimpleTestCase):

    def test_property_name_expression(self):
        for constant in (7.2, 'hello world', ['a', 'list'], {'a': 'dict'}):
            getter = ExpressionFactory.from_spec({
                'type': 'constant',
                'constant': constant,
            })
            self.assertEqual(constant, getter({}))
            self.assertEqual(constant, getter({'some': 'random stuff'}))

    def test_invalid_constant(self):
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec({
                'type': 'constant',
            })


class ExpressionFromSpecTest(SimpleTestCase):

    def test_invalid_type(self):
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec({
                'type': 'not_a_valid_type',
            })

    def test_property_name_expression(self):
        getter = ExpressionFactory.from_spec({
            'type': 'property_name',
            'property_name': 'foo',
        })
        self.assertEqual(DictGetter, type(getter))
        self.assertEqual('foo', getter.property_name)

    def test_property_name_no_name(self):
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec({
                'type': 'property_name',
            })

    def test_property_name_empty_name(self):
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec({
                'type': 'property_name',
                'property_name': None,
            })

    def test_property_path_expression(self):
        getter = ExpressionFactory.from_spec({
            'type': 'property_path',
            'property_path': ['path', 'to', 'foo'],
        })
        self.assertEqual(NestedDictGetter, type(getter))
        self.assertEqual(['path', 'to', 'foo'], getter.property_path)

    def test_property_path_no_path(self):
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec({
                'type': 'property_path',
            })

    def test_property_path_empty_path(self):
        for empty_path in ([], None):
            with self.assertRaises(BadSpecError):
                ExpressionFactory.from_spec({
                    'type': 'property_path',
                    'property_path': empty_path,
                })


class ConditionalExpressionTest(SimpleTestCase):

    def setUp(self):
        # this expression is the equivalent to:
        #   doc.true_value if doc.test == 'match' else doc.false_value
        spec = {
            'type': 'conditional',
            'test': {
                # any valid filter can go here
                'type': 'boolean_expression',
                'expression': {
                    'type': 'property_name',
                    'property_name': 'test',
                },
                'operator': 'eq',
                'property_value': 'match',
            },
            'expression_if_true': {
                'type': 'property_name',
                'property_name': 'true_value',
            },
            'expression_if_false': {
                'type': 'property_name',
                'property_name': 'false_value',
            },
        }
        self.expression = ExpressionFactory.from_spec(spec)

    def testConditionIsTrue(self):
        self.assertEqual('correct', self.expression({
            'test': 'match',
            'true_value': 'correct',
            'false_value': 'incorrect',
        }))

    def testConditionIsFalse(self):
        self.assertEqual('incorrect', self.expression({
            'test': 'non-match',
            'true_value': 'correct',
            'false_value': 'incorrect',
        }))

    def testConditionIsMissing(self):
        self.assertEqual('incorrect', self.expression({
            'true_value': 'correct',
            'false_value': 'incorrect',
        }))

    def testResultIsMissing(self):
        self.assertEqual(None, self.expression({
            'test': 'match',
            'false_value': 'incorrect',
        }))


class BaseDocExpressionTest(SimpleTestCase):

    def setUp(self):
        spec = {
            "type": "base_doc",
            "expression": {
                "type": "property_name",
                "property_name": "base_property"
            }
        }
        self.expression = ExpressionFactory.from_spec(spec)

    def test_missing_context(self):
        self.assertEqual(None, self.expression({
            "base_property": "item_value"
        }))

    def test_not_in_context(self):
        self.assertEqual(
            None,
            self.expression(
                {"base_property": "item_value"},
                context=EvaluationContext({})
            )
        )

    def test_comes_from_context(self):
        self.assertEqual(
            "base_value",
            self.expression(
                {"base_property": "item_value"},
                context=EvaluationContext({"base_property": "base_value"})
            )
        )
