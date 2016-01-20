import copy
from datetime import date, datetime
from decimal import Decimal
from django.test import SimpleTestCase
from fakecouch import FakeCouchDb
from casexml.apps.case.models import CommCareCase
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.expressions.specs import (
    PropertyNameGetterSpec,
    PropertyPathGetterSpec,
)
from corehq.apps.userreports.specs import EvaluationContext
from corehq.util.test_utils import generate_cases


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


class IdentityExpressionTest(SimpleTestCase):

    def setUp(self):
        self.expression = ExpressionFactory.from_spec({'type': 'identity'})

    def test_identity(self):
        for obj in (7.2, 'hello world', ['a', 'list'], {'a': 'dict'}):
            self.assertEqual(obj, self.expression(obj))


class ConstantExpressionTest(SimpleTestCase):

    def test_constant_expression(self):
        for constant in (None, 7.2, 'hello world', ['a', 'list'], {'a': 'dict'}):
            getter = ExpressionFactory.from_spec({
                'type': 'constant',
                'constant': constant,
            })
            self.assertEqual(constant, getter({}))
            self.assertEqual(constant, getter({'some': 'random stuff'}))

    def test_constant_auto_detection(self):
        for valid_constant in (7.2, 'hello world', 3, True):
            getter = ExpressionFactory.from_spec(valid_constant)
            self.assertEqual(valid_constant, getter({}))
            self.assertEqual(valid_constant, getter({'some': 'random stuff'}))

    def test_constant_date_conversion(self):
        self.assertEqual(date(2015, 2, 4), ExpressionFactory.from_spec('2015-02-04')({}))

    def test_constant_datetime_conversion(self):
        self.assertEqual(datetime(2015, 2, 4, 11, 5, 24), ExpressionFactory.from_spec('2015-02-04T11:05:24Z')({}))

    def test_constant_auto_detection_invalid_types(self):
        for invalid_constant in ({}):
            with self.assertRaises(BadSpecError):
                ExpressionFactory.from_spec(invalid_constant)

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
            (u"fo\u00E9", "string", u"fo\u00E9"),
            (date(2015, 9, 30), "date", "2015-09-30"),
            (None, "date", "09/30/2015"),
            (datetime(2015, 9, 30, 19, 4, 27), "datetime", "2015-09-30T19:04:27Z"),
            (datetime(2015, 9, 30, 19, 4, 27, 113609), "datetime", "2015-09-30T19:04:27.113609Z"),
            (None, "datetime", "2015-09-30 19:04:27Z"),
            (date(2015, 9, 30), "date", "2015-09-30T19:04:27Z"),
            (date(2015, 9, 30), "date", datetime(2015, 9, 30)),
            (None, "datetime", "2015-09-30"),
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
        self.spec = {
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
        self.expression = ExpressionFactory.from_spec(self.spec)

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

    def test_literals(self):
        spec = copy.copy(self.spec)
        spec['expression_if_true'] = 'true literal'
        spec['expression_if_false'] = 'false literal'
        expression_with_literals = ExpressionFactory.from_spec(spec)
        self.assertEqual('true literal', expression_with_literals({
            'test': 'match',
        }))
        self.assertEqual('false literal', expression_with_literals({
            'test': 'non-match',
        }))


class SwitchExpressionTest(SimpleTestCase):

    def setUp(self):
        spec = {
            'type': 'switch',
            'switch_on': {
                'type': 'property_name',
                'property_name': 'test',
            },
            'cases': {
                'strawberry': {
                    'type': 'constant',
                    'constant': 'banana'
                },
                'apple': {
                    'type': 'property_name',
                    'property_name': 'apple'
                }
            },
            'default': {
                'type': 'constant',
                'constant': 'orange'
            },
        }
        self.expression = ExpressionFactory.from_spec(spec)

    def testCases(self):
        self.assertEqual('banana', self.expression({
            'test': 'strawberry',
        }))
        self.assertEqual('foo', self.expression({
            'test': 'apple',
            'apple': 'foo'
        }))
        self.assertEqual(None, self.expression({
            'test': 'apple',
        }))

    def testDefault(self):
        self.assertEqual('orange', self.expression({
            'test': 'value not in cases',
        }))


class ArrayIndexExpressionTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        cls.expression_spec = {
            'type': 'array_index',
            'array_expression': {
                'type': 'property_name',
                'property_name': 'my_array'
            },
            'index_expression': {
                'type': 'property_name',
                'property_name': 'my_index',
            },
        }
        cls.expression = ExpressionFactory.from_spec(cls.expression_spec)

    def test_basic(self):
        array = ['first', 'second', 'third']
        for i, value in enumerate(array):
            self.assertEqual(value, self.expression({'my_array': array, 'my_index': i}))

    def test_array_out_of_bounds(self):
        self.assertEqual(None, self.expression({'my_array': [], 'my_index': 1}))

    def test_array_not_an_array(self):
        self.assertEqual(None, self.expression({'my_array': {}, 'my_index': 1}))

    def test_array_empty(self):
        self.assertEqual(None, self.expression({'my_array': None, 'my_index': 1}))

    def test_invalid_index(self):
        self.assertEqual(None, self.expression({'my_array': [], 'my_index': 'troll'}))

    def test_empty_index(self):
        self.assertEqual(None, self.expression({'my_array': [], 'my_index': None}))

    def test_empty_constant_index(self):
        spec = copy.copy(self.expression_spec)
        spec['index_expression'] = 1
        expression = ExpressionFactory.from_spec(spec)
        array = ['first', 'second', 'third']
        self.assertEqual('second', expression({'my_array': array}))


class DictExpressionTest(SimpleTestCase):

    def setUp(self):
        self.expression_spec = {
            "type": "dict",
            "properties": {
                "name": "the_name",
                "value": {
                    "type": "property_name",
                    "property_name": "prop"
                }
            }
        }
        self.expression = ExpressionFactory.from_spec(self.expression_spec)

    def test_missing_properties(self):
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec({
                "type": "dict",
            })

    def test_bad_properties_type(self):
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec({
                "type": "dict",
                "properties": "bad!"
            })

    def test_empty_properties(self):
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec({
                "type": "dict",
                "properties": {},
            })

    def test_non_string_keys(self):
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec({
                "type": "dict",
                "properties": {
                    (1, 2): 2
                },
            })

    def test_basic(self):
        value = self.expression({"prop": "p_value"})
        self.assertTrue(isinstance(value, dict))
        self.assertEqual('the_name', value['name'])
        self.assertEqual('p_value', value['value'])


class NestedExpressionTest(SimpleTestCase):

    def test_basic(self):
        expression = ExpressionFactory.from_spec({
            "type": "nested",
            "argument_expression": {
                "type": "property_name",
                "property_name": "outer"
            },
            "value_expression": {
                "type": "property_name",
                "property_name": "inner"
            }
        })
        self.assertEqual('value', expression({
            "outer": {
                "inner": "value",
            }
        }))

    def test_parent_case_id(self):
        expression = ExpressionFactory.from_spec({
            "type": "nested",
            "argument_expression": {
                "type": "array_index",
                "array_expression": {
                    "type": "property_name",
                    "property_name": "indices"
                },
                "index_expression": {
                    "type": "constant",
                    "constant": 0
                }
            },
            "value_expression": {
                "type": "property_name",
                "property_name": "referenced_id"
            }
        })
        self.assertEqual(
            'my_parent_id',
            expression({
                "indices": [
                    {
                        "doc_type": "CommCareCaseIndex",
                        "identifier": "parent",
                        "referenced_type": "pregnancy",
                        "referenced_id": "my_parent_id"
                    }
                ],
            })
        )


class IteratorExpressionTest(SimpleTestCase):

    def setUp(self):
        self.spec = {
            "type": "iterator",
            "expressions": [
                {
                    "type": "property_name",
                    "property_name": "p1"
                },
                {
                    "type": "property_name",
                    "property_name": "p2"
                },
                {
                    "type": "property_name",
                    "property_name": "p3"
                },
            ],
            "test": {}
        }
        self.expression = ExpressionFactory.from_spec(self.spec)

    def test_basic(self):
        self.assertEqual([1, 2, 3], self.expression({'p1': 1, 'p2': 2, 'p3': 3}))

    def test_missing_values_default(self):
        self.assertEqual([1, 2, None], self.expression({'p1': 1, 'p2': 2}))

    def test_missing_values_filtered(self):
        spec = copy.copy(self.spec)
        spec['test'] = {
            'type': 'boolean_expression',
            'expression': {
                'type': 'identity',
            },
            'operator': 'not_eq',
            'property_value': None,
        }
        expression = ExpressionFactory.from_spec(spec)
        self.assertEqual([1, 2], expression({'p1': 1, 'p2': 2}))
        self.assertEqual([1, 3], expression({'p1': 1, 'p3': 3}))
        self.assertEqual([1], expression({'p1': 1}))
        self.assertEqual([], expression({}))

    def test_missing_and_filtered(self):
        spec = copy.copy(self.spec)
        spec['test'] = {
            "type": "not",
            "filter": {
                'type': 'boolean_expression',
                'expression': {
                    'type': 'identity',
                },
                'operator': 'in',
                'property_value': ['', None],
            }
        }
        expression = ExpressionFactory.from_spec(spec)
        self.assertEqual([1], expression({'p1': 1, 'p2': ''}))


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
        # we have to set the fake database before any other calls
        self.orig_db = CommCareCase.get_db()
        self.database = FakeCouchDb()
        CommCareCase.set_db(self.database)
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

    def tearDown(self):
        CommCareCase.set_db(self.orig_db)

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

    def test_fail_on_bad_doc_type(self):
        spec = {
            "type": "related_doc",
            "related_doc_type": "BadDocument",
            "doc_id_expression": {
                "type": "property_name",
                "property_name": "parent_id"
            },
            "value_expression": {
                "type": "property_name",
                "property_name": "related_property"
            }
        }
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec(spec)

    def test_caching(self):
        self.test_simple_lookup()

        my_doc = self.database.get('my-id')
        self.database.mock_docs.clear()

        self.assertEqual({}, self.database.mock_docs)
        self.assertEqual('foo', self.expression(my_doc, EvaluationContext(my_doc, 0)))

        same_expression = ExpressionFactory.from_spec(self.spec)
        self.assertEqual('foo', same_expression(my_doc, EvaluationContext(my_doc, 0)))


@generate_cases([
    ({'dob': '2015-01-20'}, 3, date(2015, 1, 23)),
    ({'dob': '2015-01-20'}, 5, date(2015, 1, 25)),
    ({'dob': date(2015, 1, 20)}, 3, date(2015, 1, 23)),
    ({'dob': datetime(2015, 1, 20)}, 3, date(2015, 1, 23)),
    ({'dob': datetime(2015, 1, 20)}, 3.0, date(2015, 1, 23)),
    ({'dob': datetime(2015, 1, 20)}, '3.0', date(2015, 1, 23)),
    (
        {'dob': datetime(2015, 1, 20), 'days': '3'},
        {'type': 'property_name', 'property_name': 'days'},
        date(2015, 1, 23)
    ),
])
def test_add_days_to_date_expression(self, source_doc, count_expression, expected_value):
    expression = ExpressionFactory.from_spec({
        'type': 'add_days',
        'date_expression': {
            'type': 'property_name',
            'property_name': 'dob',
        },
        'count_expression': count_expression
    })
    self.assertEqual(expected_value, expression(source_doc))
