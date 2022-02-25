from testil import eq

from .parser import parser
from .ast import BinaryExpression, Function, Name, Literal


def test_ccql_parser():
    def _verify(expression, expected):
        ast = parser.parse(expression)
        eq(ast, expected)

    for op in (">", ">=", "<", "<=", "=", "!="):
        yield _verify, f"a {op} 1", BinaryExpression(Name("a"), op, Literal(1))

    a_eq_1 = BinaryExpression(Name("a"), "=", Literal(1))
    b_eq_2 = BinaryExpression(Name("b"), "=", Literal(2))
    c_eq_3 = BinaryExpression(Name("c"), "=", Literal(3))
    d_eq_4 = BinaryExpression(Name("d"), "=", Literal(4))

    for op in ("and", "or"):
        yield _verify, f"a=1 {op} b=2", BinaryExpression(
            a_eq_1, op, b_eq_2
        )

    yield from [
        (_verify, "age > 3", BinaryExpression(Name("age"), ">", Literal(3))),  # int value
        (_verify, "a = 'x'", BinaryExpression(Name("a"), "=", Literal("x"))),  # string value
        (_verify, "a = 5.63", BinaryExpression(Name("a"), "=", Literal(5.63))),  # float value
        (_verify, "a = date('the future')", BinaryExpression(
            Name("a"), "=", Function(Name("date"), (Literal("the future"),)))),  # function value
        (_verify, "(a=1 and b=2) and c=3", BinaryExpression(
            BinaryExpression(a_eq_1, "and", b_eq_2),
            "and", c_eq_3)),  # group
        (_verify, "(a=1 and (b=2 or c=3)) and d=4", BinaryExpression(
            BinaryExpression(a_eq_1, "and", BinaryExpression(b_eq_2, "or", c_eq_3)),
            "and", d_eq_4))
        # "(age > 3 and age < 10) and region = 'chamonix'",
        # "dob > date('2018-01-03')",
        # "not(age > 10)",
        # "age < 3 or (age > 10 and not(danger = 1))",
        # "name = 'bob' and {age > 3 and name != 'bob'}.subcase('parent').exists()",
        # "parent/parent/age = 4",
        # "selected-all(property, 'a b c')"
    ]
