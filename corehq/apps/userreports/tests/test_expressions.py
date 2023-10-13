import copy
import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase
from testil import Config

from casexml.apps.case.const import CASE_INDEX_EXTENSION
from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from corehq.apps.groups.models import Group
from corehq.apps.userreports.decorators import ucr_context_cache
from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.expressions.specs import (
    PropertyNameGetterSpec,
    PropertyPathGetterSpec,
)
from corehq.apps.userreports.specs import EvaluationContext, FactoryContext
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.util.test_utils import (
    create_and_save_a_case,
    create_and_save_a_form,
    generate_cases,
)


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
        # this is due to the type conversion in JsonObject
        self.assertEqual(date(2015, 2, 4), ExpressionFactory.from_spec('2015-02-04')({}))

    def test_constant_datetime_conversion(self):
        # this is due to the type conversion in JsonObject
        self.assertEqual(datetime(2015, 2, 4, 11, 5, 24), ExpressionFactory.from_spec('2015-02-04T11:05:24Z')({}))

    def test_legacy_constant_no_type_casting(self):
        """
        This test is used to document an unexpected legacy behavior of
            ucr constant expression not honoring type casting. While changing that
            behavior would be easy, it might break any existing reports that relied
            on the broken implementation as a feature, and so is left as-is.
        """
        self.assertEqual(
            ExpressionFactory.from_spec({
                'constant': '2018-01-03',
                'datatype': 'string',
                'type': 'constant'
            })({}),
            date(2018, 1, 3)
        )

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
            ("fo\u00E9", "string", "fo\u00E9"),
            (date(2015, 9, 30), "date", "2015-09-30"),
            (None, "date", "09/30/2015"),
            (datetime(2015, 9, 30, 19, 4, 27), "datetime", "2015-09-30T19:04:27Z"),
            (datetime(2015, 9, 30, 19, 4, 27, 113609), "datetime", "2015-09-30T19:04:27.113609Z"),
            (datetime(2015, 9, 30, 19, 4, 27), "datetime", "2015-09-30 19:04:27Z"),
            (date(2015, 9, 30), "date", "2015-09-30T19:04:27Z"),
            (date(2015, 9, 30), "date", datetime(2015, 9, 30)),
            ('2015-09-30', "string", date(2015, 9, 30)),
            (datetime(2015, 9, 30, 0, 0, 0), "datetime", "2015-09-30"),
            ([None], "array", None),
            ([3], "array", 3),
            ([3, 4, 9], "array", [3, 4, 9]),
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


class PropertyNameExpressionTest(SimpleTestCase):
    def test_basic(self):
        wrapped_expression = ExpressionFactory.from_spec({
            'type': 'property_name',
            'property_name': 'foo'
        })
        self.assertEqual(wrapped_expression({'foo': 'foo_value'}), 'foo_value')
        self.assertEqual(wrapped_expression({'no': 'value'}), None)

    def test_property_name_expression_with_expression(self):
        wrapped_expression = ExpressionFactory.from_spec({
            'type': 'property_name',
            'property_name': {
                'type': 'constant',
                'constant': 'foo',
            }
        })
        self.assertEqual(wrapped_expression({'foo': 'foo_value'}), 'foo_value')


class PropertyPathExpressionTest(SimpleTestCase):

    def test_datatype(self):
        spec = {
            'type': 'property_path',
            'property_path': ['path', 'to', 'foo'],
        }
        item = {
            'path': {'to': {'foo': '1.0'}}
        }
        tests = (
            ('string', '1.0'),
            ('decimal', Decimal(1.0)),
            ('integer', 1)
        )
        for datatype, value in tests:
            spec['datatype'] = datatype
            self.assertEqual(value, ExpressionFactory.from_spec(spec)(item))

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


class JsonpathExpressionTest(SimpleTestCase):

    def test_jsonpath(self):
        """test examples in docs"""
        spec = {
            'type': 'jsonpath',
            'jsonpath': 'form..case.name'
        }
        item = {
            "form": {
                "case": {"name": "a"},
                "nested": {
                    "case": {"name": "b"},
                },
                "list": [
                    {"case": {"name": "c"}},
                    {
                        "nested": {
                            "case": {"name": "d"}
                        }
                    }
                ]
            }
        }
        self.assertEqual(["a", "b", "c", "d"], ExpressionFactory.from_spec(spec)(item))
        spec['jsonpath'] = 'form.list[0].case.name'
        self.assertEqual("c", ExpressionFactory.from_spec(spec)(item))

    def test_bad_expression(self):
        with self.assertRaises(BadSpecError):
            ExpressionFactory.from_spec({
                'type': 'jsonpath',
                'jsonpath': 'find("a" in "b")'
            })

    @generate_cases([(None,), ('',), ([],)])
    def test_bad_values(self, bad_value):
        expr = ExpressionFactory.from_spec({
            'type': 'jsonpath',
            'jsonpath': 'a.b.c'
        })
        self.assertEqual(None, expr({
            'a': {
                'b': bad_value
            }
        }))

    @generate_cases([
        ({"a": "1"}, "a", "integer", 1),
        ({"a": [{"b": "1"}, {"b": "2"}, {"b": "x"}]}, "a..b", "integer", [1, 2, None]),
        ({"a": {"b": 1}}, "a..b", "array", [1]),
        ({"a": "foo5+3bar"}, "a.`sub(/(foo\\\\d+)\\\\+(\\\\d+bar)/, \\\\2-\\\\1)`", "string", "3bar-foo5"),
        ({"a": "foo", "b": "bar"}, "$.a + '_' + $.b", "string", "foo_bar"),
    ])
    def test_datatype(self, item, jsonpath, datatype, expected):
        expr = ExpressionFactory.from_spec({
            'type': 'jsonpath',
            'jsonpath': jsonpath,
            'datatype': datatype
        })
        self.assertEqual(expected, expr(item))

    @generate_cases([
        ({"a": 1}, "a", 1),
        ({"a": [1, 2, 3]}, "a", [1, 2, 3]),
        ({"a": [{"b": 1}, {"b": 2}]}, "a..b", [1, 2]),
        ({"a": {"b": 1}}, "a..b", 1),
    ])
    def test_list_coersion(self, item, jsonpath, expected):
        expr = ExpressionFactory.from_spec({
            'type': 'jsonpath',
            'jsonpath': jsonpath,
        })
        self.assertEqual(expected, expr(item))


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
            'default': 'orange',
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
        super(ArrayIndexExpressionTest, cls).setUpClass()
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

    def test_nested_date(self):
        spec = {
            'type': 'array_index',
            'array_expression': {
                'type': 'iterator',
                'expressions': [
                    {
                        'constant': '2018-01-01',
                        'datatype': 'date',
                        'type': 'constant'
                    },
                    '2018-01-02',
                    {
                        'constant': '2018-01-03',
                        'datatype': 'string',
                        'type': 'constant'
                    },
                    'not-date'
                ]
            },
            'index_expression': 0
        }
        # date expression should be captured as date
        expression = ExpressionFactory.from_spec(spec)
        self.assertEqual(expression({}), date(2018, 1, 1))
        # literal date should be captured as date
        spec['index_expression'] = 1
        expression = ExpressionFactory.from_spec(spec)
        self.assertEqual(expression({}), date(2018, 1, 2))
        # date expression cast to string is also captured as date.
        #   see note on ConstantExpressionTest.test_legacy_constant_no_type_casting
        spec['index_expression'] = 2
        expression = ExpressionFactory.from_spec(spec)
        self.assertEqual(expression({}), date(2018, 1, 3))
        # string is captured as string
        spec['index_expression'] = 3
        expression = ExpressionFactory.from_spec(spec)
        self.assertEqual(expression({}), 'not-date')


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

    def test_name_in_argument(self):
        expression = ExpressionFactory.from_spec(
            {
                "type": "nested",
                "argument_expression": {
                    "type": "named",
                    "name": "three"
                },
                "value_expression": {
                    "type": "identity",
                }
            },
            FactoryContext({'three': ExpressionFactory.from_spec(3)}, {})
        )
        self.assertEqual(3, expression({}))

    def test_name_in_value(self):
        expression = ExpressionFactory.from_spec(
            {
                "type": "nested",
                "argument_expression": {
                    "type": "identity",
                },
                "value_expression": {
                    "type": "named",
                    "name": "three"
                }
            },
            FactoryContext({'three': ExpressionFactory.from_spec(3)}, {})
        )
        self.assertEqual(3, expression({}))

    def test_caching(self):
        doc = {
            "indices": [
                {
                    "doc_type": "CommCareCaseIndex",
                    "identifier": "parent",
                    "referenced_type": "pregnancy",
                    "referenced_id": "my_parent_id"
                },
                {
                    "doc_type": "CommCareCaseIndex",
                    "identifier": "parent",
                    "referenced_type": "pregnancy",
                    "referenced_id": "my_parent_id2"
                }
            ]
        }

        named_expression = {
            "type": "property_name",
            "property_name": "referenced_id"
        }

        evaluation_context = EvaluationContext(doc)
        factory_context = FactoryContext({
            'test_named_expression': ExpressionFactory.from_spec(named_expression)
        }, {})

        expression1 = ExpressionFactory.from_spec(
            {
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
                    "type": "named",
                    "name": "test_named_expression"
                }
            },
            factory_context
        )
        expression2 = ExpressionFactory.from_spec(
            {
                "type": "nested",
                "argument_expression": {
                    "type": "array_index",
                    "array_expression": {
                        "type": "property_name",
                        "property_name": "indices"
                    },
                    "index_expression": {
                        "type": "constant",
                        "constant": 1
                    }
                },
                "value_expression": {
                    "type": "named",
                    "name": "test_named_expression"
                }
            },
            factory_context
        )
        self.assertEqual(expression1(doc, evaluation_context), 'my_parent_id')
        self.assertEqual(expression2(doc, evaluation_context), 'my_parent_id2')


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

    def test_type_coercion(self):
        spec = copy.copy(self.spec)
        spec['expressions'] = [
            '2018-01-01',
            {
                'type': 'constant',
                'constant': '2018-01-01',
                'datatype': 'date',
            },
        ]
        expression = ExpressionFactory.from_spec(spec)
        self.assertEqual([date(2018, 1, 1), date(2018, 1, 1)], expression({}))


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
                EvaluationContext({}, 0)
            )
        )

    def test_comes_from_context(self):
        self.assertEqual(
            "base_value",
            self.expression(
                {"base_property": "item_value"},
                EvaluationContext({"base_property": "base_value"}, 0)
            )
        )


class RelatedDocExpressionTest(SimpleTestCase):

    def setUp(self):
        # we have to set the fake database before any other calls
        self.patch_cases_database()
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

    def patch_cases_database(self):
        def get_case(case_id, domain):
            doc = self.database.get(case_id)
            if doc is None:
                raise CaseNotFound
            return Config(to_json=lambda: doc)
        get_case_patch = patch.object(CommCareCase.objects, "get_case", get_case)
        get_case_patch.start()
        self.addCleanup(get_case_patch.stop)
        self.database = {}

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
        self.database = {
            'my-id': my_doc,
            related_id: related_doc
        }
        self.assertEqual('foo', self.expression(my_doc, EvaluationContext(my_doc, 0)))

    def test_related_doc_not_found(self):
        doc = {'parent_id': 'some-missing-id', 'domain': 'whatever'}
        self.assertEqual(None, self.expression(doc, EvaluationContext(doc, 0)))

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
        self.database = {
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
        self.database = {
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
        self.database = {
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

        context = EvaluationContext(my_doc, 0)
        self.assertEqual('foo', self.expression(my_doc, context))

        my_doc = self.database.get('my-id')
        self.database.clear()
        self.assertEqual('foo', self.expression(my_doc, context))


class RelatedDocExpressionDbTest(TestCase):
    domain = 'related-doc-db-test-domain'

    def test_form_lookups(self):
        form = create_and_save_a_form(domain=self.domain)
        expression = self._get_expression('XFormInstance')
        doc = self._get_doc(form.form_id)
        self.assertEqual(form.form_id, expression(doc, EvaluationContext(doc, 0)))

    def test_case_lookups(self):
        case_id = uuid.uuid4().hex
        create_and_save_a_case(domain=self.domain, case_id=case_id, case_name='related doc test case')
        expression = self._get_expression('CommCareCase')
        doc = self._get_doc(case_id)
        self.assertEqual(case_id, expression(doc, EvaluationContext(doc, 0)))

    def test_other_lookups(self):
        user_id = uuid.uuid4().hex
        CommCareUser.get_db().save_doc({'_id': user_id, 'domain': self.domain})
        expression = self._get_expression('CommCareUser')
        doc = self._get_doc(user_id)
        self.assertEqual(user_id, expression(doc, EvaluationContext(doc, 0)))

    @staticmethod
    def _get_expression(doc_type):
        return ExpressionFactory.from_spec({
            "type": "related_doc",
            "related_doc_type": doc_type,
            "doc_id_expression": {
                "type": "property_name",
                "property_name": "related_id"
            },
            "value_expression": {
                "type": "property_name",
                "property_name": "_id"
            }
        })

    @classmethod
    def _get_doc(cls, id):
        return {
            'related_id': id,
            'domain': cls.domain,
        }


class TestFormsExpressionSpec(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestFormsExpressionSpec, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        factory = CaseFactory(domain=cls.domain)
        [cls.case] = factory.create_or_update_case(CaseStructure(attrs={'create': True}))
        cls.forms = [f.to_json() for f in XFormInstance.objects.get_forms(cls.case.xform_ids, cls.domain)]
        #  redundant case to create extra forms that shouldn't be in the results for cls.case
        [cls.case_b] = factory.create_or_update_case(CaseStructure(attrs={'create': True}))

    @classmethod
    def tearDownClass(cls):
        delete_all_xforms()
        delete_all_cases()
        super(TestFormsExpressionSpec, cls).tearDownClass()

    def _make_expression(self, xmlns=None):
        spec = {
            "type": "get_case_forms",
            "case_id_expression": {
                "type": "property_name",
                "property_name": "_id"
            },
        }
        if xmlns:
            spec['xmlns'] = [xmlns]
        return ExpressionFactory.from_spec(spec)

    def test_evaluation(self):
        expression = self._make_expression()
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)

        self.assertEqual(len(forms), 1)
        self.assertEqual(forms, self.forms)

    def test_wrong_domain(self):
        expression = self._make_expression()
        context = EvaluationContext({"domain": "wrong-domain"}, 0)
        forms = expression(self.case.to_json(), context)
        self.assertEqual(forms, [])

    def test_correct_xmlns(self):
        expression = self._make_expression('http://commcarehq.org/case')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)
        self.assertEqual(len(forms), 1)
        self.assertEqual(forms, self.forms)

    def test_incorrect_xmlns(self):
        expression = self._make_expression('silly-xmlns')
        context = EvaluationContext({"domain": self.domain}, 0)
        forms = expression(self.case.to_json(), context)
        self.assertEqual(forms, [])


class TestGetSubcasesExpression(TestCase):

    def setUp(self):
        super(TestGetSubcasesExpression, self).setUp()
        self.domain = uuid.uuid4().hex
        self.factory = CaseFactory(domain=self.domain)
        self.expression = ExpressionFactory.from_spec({
            "type": "get_subcases",
            "case_id_expression": {
                "type": "property_name",
                "property_name": "_id"
            },
        })
        self.context = EvaluationContext({"domain": self.domain})

    def tearDown(self):
        delete_all_xforms()
        delete_all_cases()
        super(TestGetSubcasesExpression, self).tearDown()

    def test_no_subcases(self):
        case = self.factory.create_case()
        subcases = self.expression(case.to_json(), self.context)
        self.assertEqual(len(subcases), 0)

    def test_single_child(self):
        parent_id = uuid.uuid4().hex
        child_id = uuid.uuid4().hex
        [child, parent] = self.factory.create_or_update_case(CaseStructure(
            case_id=child_id,
            indices=[
                CaseIndex(CaseStructure(case_id=parent_id, attrs={'create': True}))
            ],
            attrs={'create': True}
        ))
        subcases = self.expression(parent.to_json(), self.context)
        self.assertEqual(len(subcases), 1)
        self.assertEqual(child.case_id, subcases[0]['_id'])

    def test_single_extension(self):
        host_id = uuid.uuid4().hex
        extension_id = uuid.uuid4().hex
        [extension, host] = self.factory.create_or_update_case(CaseStructure(
            case_id=extension_id,
            indices=[
                CaseIndex(
                    CaseStructure(case_id=host_id, attrs={'create': True}),
                    relationship=CASE_INDEX_EXTENSION
                )
            ],
            attrs={'create': True}
        ))
        subcases = self.expression(host.to_json(), self.context)
        self.assertEqual(len(subcases), 1)
        self.assertEqual(extension.case_id, subcases[0]['_id'])


class TestGetCaseSharingGroupsExpression(TestCase):

    def setUp(self):
        super(TestGetCaseSharingGroupsExpression, self).setUp()
        self.domain = uuid.uuid4().hex
        self.second_domain = uuid.uuid4().hex
        self.expression = ExpressionFactory.from_spec({
            "type": "get_case_sharing_groups",
            "user_id_expression": {
                "type": "property_name",
                "property_name": "user_id"
            },
        })
        self.context = EvaluationContext({"domain": self.domain})

    def tearDown(self):
        for group in Group.by_domain(self.domain):
            group.delete()
        for group in Group.by_domain(self.second_domain):
            group.delete()
        for user in CommCareUser.all():
            user.delete(self.domain, deleted_by=None)
        super(TestGetCaseSharingGroupsExpression, self).tearDown()

    def test_no_groups(self):
        user = CommCareUser.create(domain=self.domain, username='test_no_group', password='123',
                                   created_by=None, created_via=None)
        case_sharing_groups = self.expression({'user_id': user._id}, self.context)
        self.assertEqual(len(case_sharing_groups), 0)

    def test_single_group(self):
        user = CommCareUser.create(domain=self.domain, username='test_single', password='123',
                                   created_by=None, created_via=None)
        group = Group(domain=self.domain, name='group_single', users=[user._id], case_sharing=True)
        group.save()

        case_sharing_groups = self.expression({'user_id': user._id}, self.context)
        self.assertEqual(len(case_sharing_groups), 1)
        self.assertEqual(group._id, case_sharing_groups[0]['_id'])

    def test_multiple_groups(self):
        user = CommCareUser.create(domain=self.domain, username='test_multiple', password='123',
                                   created_by=None, created_via=None)
        group1 = Group(domain=self.domain, name='group1', users=[user._id], case_sharing=True)
        group1.save()
        group2 = Group(domain=self.domain, name='group2', users=[user._id], case_sharing=True)
        group2.save()

        case_sharing_groups = self.expression({'user_id': user._id}, self.context)
        self.assertEqual(len(case_sharing_groups), 2)

    def test_wrong_domain(self):
        user = CommCareUser.create(domain=self.second_domain, username='test_wrong_domain', password='123',
                                   created_by=None, created_via=None)
        group = Group(domain=self.second_domain, name='group_wrong_domain', users=[user._id], case_sharing=True)
        group.save()

        case_sharing_groups = self.expression({'user_id': user._id}, self.context)
        self.assertEqual(len(case_sharing_groups), 0)

    def test_web_user(self):
        user = WebUser.create(domain=None, username='web', password='123',
                              created_by=None, created_via=None)
        case_sharing_groups = self.expression({'user_id': user._id}, self.context)
        self.assertEqual(len(case_sharing_groups), 0)


class TestGetReportingGroupsExpression(TestCase):

    def setUp(self):
        super(TestGetReportingGroupsExpression, self).setUp()
        self.domain = uuid.uuid4().hex
        self.second_domain = uuid.uuid4().hex
        self.expression = ExpressionFactory.from_spec({
            "type": "get_reporting_groups",
            "user_id_expression": {
                "type": "property_name",
                "property_name": "user_id"
            },
        })
        self.context = EvaluationContext({"domain": self.domain})

    def tearDown(self):
        for group in Group.by_domain(self.domain):
            group.delete()
        for group in Group.by_domain(self.second_domain):
            group.delete()
        for user in CommCareUser.all():
            user.delete(self.domain, deleted_by=None)
        super(TestGetReportingGroupsExpression, self).tearDown()

    def test_no_groups(self):
        user = CommCareUser.create(domain=self.domain, username='test_no_group', password='123',
                                   created_by=None, created_via=None)
        reporting_groups = self.expression({'user_id': user._id}, self.context)
        self.assertEqual(len(reporting_groups), 0)

    def test_multiple_groups(self):
        user = CommCareUser.create(domain=self.domain, username='test_multiple', password='123',
                                   created_by=None, created_via=None)
        group1 = Group(domain=self.domain, name='group1', users=[user._id])
        group1.save()
        group2 = Group(domain=self.domain, name='group2', users=[user._id], case_sharing=True)
        group2.save()

        reporting_groups = self.expression({'user_id': user._id}, self.context)
        self.assertEqual(len(reporting_groups), 2)

    def test_wrong_domain(self):
        user = CommCareUser.create(domain=self.second_domain, username='test_wrong_domain', password='123',
                                   created_by=None, created_via=None)
        group = Group(domain=self.second_domain, name='group_wrong_domain', users=[user._id], case_sharing=True)
        group.save()

        reporting_groups = self.expression({'user_id': user._id}, self.context)
        self.assertEqual(len(reporting_groups), 0)


class TestIterationNumberExpression(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestIterationNumberExpression, cls).setUpClass()
        cls.spec = ExpressionFactory.from_spec({'type': 'base_iteration_number'})

    def test_default(self):
        self.assertEqual(0, self.spec({}, EvaluationContext({})))

    def test_value_set(self):
        self.assertEqual(7, self.spec({}, EvaluationContext({}, iteration=7)))


class TestEvaluationContext(SimpleTestCase):

    def test_cache(self):
        context = EvaluationContext({})
        context.set_cache_value(('k1', 'k2'), 'v1')
        self.assertEqual(context.get_cache_value(('k1', 'k2')), 'v1')
        self.assertEqual(context.get_cache_value(('k1',)), None)

    def test_cached_function(self):
        counter = MagicMock()

        @ucr_context_cache(vary_on=('arg1', 'arg2',))
        def fn_that_should_be_cached(arg1, arg2, evaluation_context):
            counter()

        context = EvaluationContext({})
        fn_that_should_be_cached(2, 2, context)
        self.assertEqual(counter.call_count, 1)
        fn_that_should_be_cached(2, 2, context)
        self.assertEqual(counter.call_count, 1)
        fn_that_should_be_cached(3, 3, context)
        self.assertEqual(counter.call_count, 2)

    def test_cached_method(self):
        counter = MagicMock()

        class MyObject(object):
            @ucr_context_cache(vary_on=('arg1', 'arg2',))
            def method_that_should_be_cached(self, arg1, arg2, evaluation_context):
                counter()

        context = EvaluationContext({})
        my_obj = MyObject()
        my_obj.method_that_should_be_cached(2, 2, context)
        self.assertEqual(counter.call_count, 1)
        my_obj.method_that_should_be_cached(2, 2, context)
        self.assertEqual(counter.call_count, 1)
        my_obj.method_that_should_be_cached(3, 3, context)
        self.assertEqual(counter.call_count, 2)

    def test_no_overlap(self):
        counter = MagicMock()

        @ucr_context_cache(vary_on=('arg1',))
        def fn_that_should_be_cached(arg1, evaluation_context):
            counter()

        @ucr_context_cache(vary_on=('arg1',))
        def another_fn_that_should_be_cached(arg1, evaluation_context):
            counter()

        context = EvaluationContext({})
        fn_that_should_be_cached(2, context)
        self.assertEqual(counter.call_count, 1)
        another_fn_that_should_be_cached(2, context)
        self.assertEqual(counter.call_count, 2)
        fn_that_should_be_cached(3, context)
        self.assertEqual(counter.call_count, 3)


class SplitStringExpressionTest(SimpleTestCase):

    def test_split_string_index_expression(self):
        for expected, string_value, index in [
            ("a", "a b c", 0),
            ("b", "a b c", 1),
            (None, "a b c", 4),
            (None, "a b c", "foo"),
            (None, "a b c", None),
            (None, None, 0),
            (None, 36, 0),
        ]:
            split_string_expression = ExpressionFactory.from_spec({
                "type": "split_string",
                "string_expression": {
                    "type": "property_name",
                    "property_name": "string_property"
                },
                "index_expression": {
                    "type": "property_name",
                    "property_name": "index_property"
                }
            })
            self.assertEqual(expected, split_string_expression({
                "string_property": string_value,
                "index_property": index
            }))

    def test_split_string_index_constant(self):
        for expected, string_value, index in [
            ("a", "a b c", 0),
            ("b", "a b c", 1),
            (None, "a b c", 4),
            (None, "a b c", "foo"),
            (None, None, 0),
            (None, 36, 0),
        ]:
            split_string_expression = ExpressionFactory.from_spec({
                "type": "split_string",
                "string_expression": {
                    "type": "property_name",
                    "property_name": "string_property"
                },
                "index_expression": index
            })
            self.assertEqual(expected, split_string_expression({"string_property": string_value}))

    def test_split_string_delimiter(self):
        for expected, string_value, index in [
            ("a", "a,b,c", 0),
            ("b", "a,b,c", 1),
            (None, "a,b,c", 4),
            (None, "a,b,c", "foo"),
            (None, None, 0),
            (None, 36, 0),
        ]:
            split_string_expression = ExpressionFactory.from_spec({
                "type": "split_string",
                "string_expression": {
                    "type": "property_name",
                    "property_name": "string_property"
                },
                "delimiter": ",",
                "index_expression": index
            })
            self.assertEqual(expected, split_string_expression({"string_property": string_value}))

    def test_split_string_delimiter_without_index(self):
        split_string_expression = ExpressionFactory.from_spec({
            "type": "split_string",
            "string_expression": {
                "type": "property_name",
                "property_name": "string_property"
            },
            "delimiter": ","
        })
        self.assertListEqual(['a', 'b', 'c'], split_string_expression({"string_property": 'a,b,c'}))


class TestCoalesceExpression(SimpleTestCase):

    def setUp(self):
        self.spec = {
            'type': 'coalesce',
            'expression': {
                'type': 'property_name',
                'property_name': 'expression'
            },
            'default_expression': {
                'type': 'property_name',
                'property_name': 'default_expression'
            },
        }
        self.expression = ExpressionFactory.from_spec(self.spec)

    def testNoCoalesce(self):
        self.assertEqual('foo', self.expression({
            'expression': 'foo',
            'default_expression': 'default',
        }))

    def testNoValue(self):
        self.assertEqual('default', self.expression({
            'default_expression': 'default',
        }))

    def testNull(self):
        self.assertEqual('default', self.expression({
            'expression': None,
            'default_expression': 'default',
        }))

    def testEmptyString(self):
        self.assertEqual('default', self.expression({
            'expression': '',
            'default_expression': 'default',
        }))

    def testZero(self):
        self.assertEqual(0, self.expression({
            'expression': 0,
            'default_expression': 'default',
        }))

    def testBlankDefaultValue(self):
        self.assertEqual('foo', self.expression({
            'expression': 'foo',
        }))

    def testBlankDefaultValue2(self):
        self.assertEqual(None, self.expression({}))
