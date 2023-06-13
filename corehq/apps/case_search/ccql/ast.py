import dataclasses
from typing import Iterable

from lark import v_args, Transformer


@dataclasses.dataclass
class BinaryExpression:
    left: object
    op: str
    right: object


@dataclasses.dataclass
class Function:
    name: "Name"
    args: Iterable


@dataclasses.dataclass
class Ancestor:
    lineage: Iterable[str]
    field: str


@dataclasses.dataclass
class Literal:
    value: object


@dataclasses.dataclass
class Name:
    value: object


def _value(self, token):
    return token.value


def _values(self, *args):
    return args


def _literal(wrapper=None):
    def _inner(self, token):
        value = wrapper(token.value) if wrapper else token.value
        return Literal(value)
    return _inner


def _strip_quotes(value):
    return value[1:-1]


@v_args(inline=True)
class CCQLTransformer(Transformer):
    INT = _literal(int)
    FLOAT = _literal(float)
    STRING = _literal(_strip_quotes)
    OP = _value
    BOP = _value
    FUNC = _value
    args = _values

    def b_expr(self, left, op, right):
        return BinaryExpression(left, op, right)

    def c_expr(self, left, op, right):
        return BinaryExpression(left, op, right)

    def function(self, name, args):
        return Function(name, args)

    def ancestor(self, *args):
        return Ancestor(args[:-1], args[-1])

    def NAME(self, arg):
        return Name(arg.value)
