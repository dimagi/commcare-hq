from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase
from simpleeval import InvalidExpression, AssignmentAttempted

from corehq.apps.userreports.exceptions import BadSpecError
from corehq.apps.userreports.expressions.evaluator import eval_statements
from corehq.apps.userreports.expressions.factory import ExpressionFactory
from corehq.apps.userreports.expressions.getters import transform_datetime
from corehq.apps.userreports.specs import EvaluationContext, FactoryContext
from corehq.tests.util.warnings import filter_warnings
from corehq.util.test_utils import (
    generate_cases,
)


@generate_cases([
    ({}, "a + b", {"a": 2, "b": 3}, 2 + 3),
    (
        {},
        "timedelta_to_seconds(a - b)",
        {
            "a": "2016-01-01T11:30:00.000000Z",
            "b": "2016-01-01T11:00:00.000000Z"
        },
        30 * 60
    ),
    # supports string manipulation
    ({}, "str(a)+'text'", {"a": 3}, "3text"),
    # context can contain expressions
    (
        {"age": 1},
        "a + b",
        {
            "a": {
                "type": "property_name",
                "property_name": "age"
            },
            "b": 5
        },
        1 + 5
    ),
    # context variable can itself be evaluation expression
    (
        {},
        "age + b",
        {
            "age": {
                "type": "evaluator",
                "statement": "a",
                "context_variables": {
                    "a": 2
                }
            },
            "b": 5
        },
        5 + 2
    ),
    ({}, "a + b", {"a": Decimal(2), "b": Decimal(3)}, Decimal(5)),
    ({}, "a + b", {"a": Decimal(2.2), "b": Decimal(3.1)}, Decimal(5.3)),
    ({}, "range(3)", {}, [0, 1, 2]),
    ({}, "today()", {}, date.today()),
    (
        {'dob': "2022-01-01T14:44:23.001567Z"},
        "f'{d}'[:-6] + '%03d' % round(int(f'{d:%f}')/1000) + 'Z'",
        {
            "d": {
                "type": "property_name",
                "property_name": "dob",
                "datatype": "datetime",
            },
        },
        '2022-01-01 14:44:23.002Z'),
])
def test_valid_eval_expression(self, source_doc, statement, context, expected_value):
    expression = ExpressionFactory.from_spec({
        "type": "evaluator",
        "statement": statement,
        "context_variables": context
    })
    if isinstance(expected_value, str):
        self.assertEqual(expression(source_doc), expected_value)
    else:
        # almostEqual handles decimal (im)precision - it means "equal to 7 places"
        self.assertAlmostEqual(expression(source_doc), expected_value)


@generate_cases([
    # context must be a dict
    ({}, "2 + 3", "text context"),
    ({}, "2 + 3", 42),
    ({}, "2 + 3", []),
    # statement must be string
    ({}, 2 + 3, {"a": 2, "b": 3})
])
def test_invalid_eval_expression(self, source_doc, statement, context):
    with self.assertRaises(BadSpecError):
        ExpressionFactory.from_spec({
            "type": "evaluator",
            "statement": statement,
            "context_variables": context
        })


@generate_cases([
    ("a + (a*b)", {"a": 2, "b": 3}, 2 + (2 * 3)),
    ("a-b", {"a": 5, "b": 2}, 5 - 2),
    ("a+b+c+9", {"a": 5, "b": 2, "c": 8}, 5 + 2 + 8 + 9),
    ("a*b", {"a": 2, "b": 23}, 2 * 23),
    ("a*b if a > b else b -a", {"a": 2, "b": 23}, 23 - 2),
    ("'text1' if a < 5 else 'text2'", {"a": 4}, 'text1'),
    ("a if a else b", {"a": 0, "b": 1}, 1),
    ("a if a else b", {"a": False, "b": 1}, 1),
    ("a if a else b", {"a": None, "b": 1}, 1),
    ("range(1, a)", {"a": 5}, [1, 2, 3, 4]),
    ("a or b", {"a": 0, "b": 1}, True),
    ("a and b", {"a": 0, "b": 1}, False),
    # ranges > 100 items aren't supported
    ("range(200)", {}, None),
    ("f'{a}'[1:3]", {"a": 1234}, "23"),
    ("a and not b", {"a": 1, "b": 0}, True),
    ("int(a)", {"a": 1.23}, 1),
    ("round(a)", {"a": 1.23}, 1),
    ("f'{a:%Y-%m-%d %H:%M}'", {"a": transform_datetime("2022-01-01T14:44:23.123123Z")}, '2022-01-01 14:44'),
    ("a + b", {"a": 'this is ', "b": 'text'}, 'this is text'),
    ("""jsonpath("indices[?id='p'].ref")""", {"indices": [{"id": "q", "ref": "2"}, {"id": "p", "ref": "1"}]}, "1"),
    ("jsonpath('i.j', context=k)", {"k": {"i": {"j": "X"}}}, "X"),
    ("jsonpath('k.i.j', as_list=True)", {"k": {"i": {"j": "X"}}}, ["X"]),
    ("context()", {"a": 1, "b": 2}, {"a": 1, "b": 2}),
    ("x = b", {"a": 1, "b": 2}, 2),  # assignment is ignored and the 'value' is returned
    ("'a %s' % a; b", {"a": 1, "b": 2}, "a 1"),  # only the first expression is executed
    ("[i for i in range(3)]", {}, [0, 1, 2]),  # list comprehension
    ("{'x': a, b: 'y'}", {"a": 1, "b": 2}, {"x": 1, 2: "y"}),  # create dict
    ("set(x)", {"x": [1, 2, 1]}, {1, 2}),
    ("[x for x in (a if a % 2 == 0 else 0 for a in range(5)) if x]", {}, [2, 4]),  # generator
    ("""{"a": 1, "b": set(cases), "c": list(range(4))}""", {
        "cases": [1, 1, 2]}, {"a": 1, "b": {1, 2}, "c": [0, 1, 2, 3]}
     ),
])
def test_supported_evaluator_statements(self, eq, context, expected_value):
    with filter_warnings("default", category=AssignmentAttempted):
        self.assertEqual(eval_statements(eq, context), expected_value)


@generate_cases([
    # missing context, b not defined
    ("a + (a*b)", {"a": 2}),
    # power function not supported
    ("a**b", {"a": 2, "b": 23}),
    # lambda not supported
    ("lambda x: x*x", {"a": 2}),
    # max function not defined
    ("max(a, b)", {"a": 3, "b": 5}),
    # method calls not allowed
    ('"WORD".lower()', {"a": 5}),
    ('f"{a.lower()}"', {"a": "b"}),
    ('{x: x for x in range(3)}', {}),  # dict comprehension
])
def test_unsupported_evaluator_statements(self, eq, context):
    with self.assertRaises(InvalidExpression):
        eval_statements(eq, context)
    expression = ExpressionFactory.from_spec({
        "type": "evaluator",
        "statement": eq,
        "context_variables": context
    })
    self.assertEqual(expression({}), None)


@generate_cases([
    ("a/b", {"a": 5, "b": None}, TypeError),
    ("a/b", {"a": 5, "b": 0}, ZeroDivisionError),
])
def test_errors_in_evaluator_statements(self, eq, context, error_type):
    with self.assertRaises(error_type):
        eval_statements(eq, context)
    expression = ExpressionFactory.from_spec({
        "type": "evaluator",
        "statement": eq,
        "context_variables": context
    })
    self.assertEqual(expression({}), None)


class TestEvaluatorTypes(SimpleTestCase):

    def test_datatype(self):
        spec = {
            "type": "evaluator",
            "statement": '1.0 + a',
            "context_variables": {'a': 1.0}
        }
        self.assertEqual(type(ExpressionFactory.from_spec(spec)({})), float)
        spec['datatype'] = 'integer'
        self.assertEqual(type(ExpressionFactory.from_spec(spec)({})), int)


class TestEvaluatorContext(SimpleTestCase):

    def test_no_context(self):
        spec = {
            "type": "evaluator",
            "statement": 'a',
        }
        self.assertEqual(ExpressionFactory.from_spec(spec)({"a": 1}), 1)

    def test_named_function(self):
        spec = {
            "type": "evaluator",
            "statement": 'named("expr1")',
        }
        factory_context = FactoryContext(named_expressions={
            "expr1": ExpressionFactory.from_spec({
                "type": "property_name",
                "property_name": "a"
            })
        }, named_filters={})
        self.assertEqual(ExpressionFactory.from_spec(spec, factory_context)({"a": 1}), 1)

    def test_root_context(self):
        spec = {
            "type": "evaluator",
            "statement": 'jsonpath("a.b", context=root_context())',
        }
        expr = ExpressionFactory.from_spec(spec)
        result = expr({"a": 1}, EvaluationContext({"a": {"b": "from root"}}))
        self.assertEqual(result, "from root")
