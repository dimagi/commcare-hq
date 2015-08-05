from decimal import Decimal
from django.test import SimpleTestCase
from fakecouch import FakeCouchDb
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.expressions.specs import (
    PropertyNameGetterSpec,
    PropertyPathGetterSpec,
    RelatedDocExpressionSpec,
)
from corehq.apps.userreports.specs import EvaluationContext


class ExpressionPluginTest(SimpleTestCase):

    def test_custom_expression(self):
        """Confirm that plugin framework is being bootstrapped."""
        ExpressionFactory.from_spec({
            "type": "abt_supervisor"
        })

    def test_double_registration(self):

        ExpressionFactory.register("foo", lambda x: x)
        with self.assertRaises(ValueError):
            ExpressionFactory.register("foo", lambda x: x * 2)


class ConstantExpressionTest(SimpleTestCase):

    def test_constant_expression(self):
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


class PropertyExpressionTest(SimpleTestCase):

    def test_boolean_to_string_conversion(self):
        getter = ExpressionFactory.from_spec({
            'type': 'property_name',
            'property_name': 'my_bool',
            'datatype': 'string'
        })
        self.assertEqual('True', getter({'my_bool': True}))
        self.assertEqual('False', getter({'my_bool': False}))

    def test_datatype(self):
        for expected, datatype, original in [
            (5, "integer", "5"),
            (5, "integer", "5.3"),
            (None, "integer", "five"),
            (Decimal(5), "decimal", "5"),
            (Decimal("5.3"), "decimal", "5.3"),
            ("5", "string", "5"),
            ("5", "string", 5),
            (u"fo\u00E9", "string", u"fo\u00E9")
        ]:
            getter = ExpressionFactory.from_spec({
                'type': 'property_name',
                'property_name': 'foo',
                'datatype': datatype
            })
            self.assertEqual(expected, getter({'foo': original}))


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
        self.assertEqual(PropertyNameGetterSpec, type(getter))
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
        self.assertEqual(PropertyPathGetterSpec, type(getter))
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


class PropertyPathExpressionTest(SimpleTestCase):

    def test_property_path_bad_type(self):
        getter = ExpressionFactory.from_spec({
            'type': 'property_path',
            'property_path': ['path', 'to', 'foo'],
        })
        self.assertEqual(PropertyPathGetterSpec, type(getter))
        for bad_value in [None, '', []]:
            self.assertEqual(None, getter({
                'path': {
                    'to': bad_value
                }
            }))


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


class RootDocExpressionTest(SimpleTestCase):

    def setUp(self):
        spec = {
            "type": "root_doc",
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
                context=EvaluationContext({}, 0)
            )
        )

    def test_comes_from_context(self):
        self.assertEqual(
            "base_value",
            self.expression(
                {"base_property": "item_value"},
                context=EvaluationContext({"base_property": "base_value"}, 0)
            )
        )


class DocJoinExpressionTest(SimpleTestCase):

    def setUp(self):
        self.spec = {
            "type": "related_doc",
            "related_doc_type": "CommCareCase",
            "doc_id_expression": {
                "type": "property_name",
                "property_name": "parent_id"
            },
            "value_expression": {
                "type": "property_name",
                "property_name": "related_property"
            }
        }
        self.expression = ExpressionFactory.from_spec(self.spec)
        self.nested_expression = ExpressionFactory.from_spec({
            "type": "related_doc",
            "related_doc_type": "CommCareCase",
            "doc_id_expression": {
                "type": "property_name",
                "property_name": "parent_id"
            },
            "value_expression": {
                "type": "related_doc",
                "related_doc_type": "CommCareCase",
                "doc_id_expression": {
                    "type": "property_name",
                    "property_name": "parent_id"
                },
                "value_expression": {
                    "type": "property_name",
                    "property_name": "related_property"
                }
            }
        })

        self.database = FakeCouchDb()
        RelatedDocExpressionSpec.db_lookup = lambda _, type: self.database

    def test_simple_lookup(self):
        related_id = 'related-id'
        my_doc = {
            'domain': 'test-domain',
            'parent_id': related_id,
        }
        related_doc = {
            'domain': 'test-domain',
            'related_property': 'foo'
        }
        self.database.mock_docs = {
            'my-id': my_doc,
            related_id: related_doc
        }
        self.assertEqual('foo', self.expression(my_doc, EvaluationContext(my_doc, 0)))

    def test_related_doc_not_found(self):
        self.assertEqual(None, self.expression({'parent_id': 'some-missing-id'}))

    def test_cross_domain_lookups(self):
        related_id = 'cross-domain-id'
        my_doc = {
            'domain': 'test-domain',
            'parent_id': related_id,
        }
        related_doc = {
            'domain': 'wrong-domain',
            'related_property': 'foo'
        }
        self.database.mock_docs = {
            'my-id': my_doc,
            related_id: related_doc
        }
        self.assertEqual(None, self.expression(my_doc, EvaluationContext(my_doc, 0)))

    def test_nested_lookup(self):
        related_id = 'nested-id-1'
        related_id_2 = 'nested-id-2'
        my_doc = {
            'domain': 'test-domain',
            'parent_id': related_id,
        }
        related_doc = {
            'domain': 'test-domain',
            'parent_id': related_id_2,
            'related_property': 'foo',
        }
        related_doc_2 = {
            'domain': 'test-domain',
            'related_property': 'bar',
        }
        self.database.mock_docs = {
            'my-id': my_doc,
            related_id: related_doc,
            related_id_2: related_doc_2
        }
        self.assertEqual('bar', self.nested_expression(my_doc, EvaluationContext(my_doc, 0)))

    def test_nested_lookup_cross_domains(self):
        related_id = 'cross-nested-id-1'
        related_id_2 = 'cross-nested-id-2'
        my_doc = {
            'domain': 'test-domain',
            'parent_id': related_id,
        }
        related_doc = {
            'domain': 'test-domain',
            'parent_id': related_id_2,
            'related_property': 'foo',
        }
        related_doc_2 = {
            'domain': 'wrong-domain',
            'related_property': 'bar',
        }
        self.database.mock_docs = {
            'my-id': my_doc,
            related_id: related_doc,
            related_id_2: related_doc_2
        }
        self.assertEqual(None, self.nested_expression(my_doc, EvaluationContext(my_doc, 0)))

    def test_caching(self):
        self.test_simple_lookup()

        my_doc = self.database.get('my-id')
        self.database.mock_docs.clear()

        self.assertEqual({}, self.database.mock_docs)
        self.assertEqual('foo', self.expression(my_doc, EvaluationContext(my_doc, 0)))

        same_expression = ExpressionFactory.from_spec(self.spec)
        self.assertEqual('foo', same_expression(my_doc, EvaluationContext(my_doc, 0)))
