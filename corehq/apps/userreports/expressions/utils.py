from __future__ import absolute_import
import copy
import operator as op
import ast
from datetime import date, datetime, timedelta
from decimal import Decimal
from types import NoneType

from simpleeval import SimpleEval, DEFAULT_OPERATORS, InvalidExpression, DEFAULT_FUNCTIONS
import six
from six.moves import range


def safe_pow_fn(a, b):
    raise InvalidExpression


def safe_range(start, *args):
    ret = list(range(start, *args))
    if len(ret) < 100:
        return ret
    return None


SAFE_OPERATORS = copy.copy(DEFAULT_OPERATORS)
SAFE_OPERATORS.update({
    ast.Pow: safe_pow_fn,  # don't allow power operations
    ast.Or: op.or_,  # Allows coalesce
    ast.And: op.and_,  # Can't have "or" without "and". Allows ternary
})

FUNCTIONS = DEFAULT_FUNCTIONS
FUNCTIONS.update({
    'timedelta_to_seconds': lambda x: x.total_seconds() if isinstance(x, timedelta) else None,
    'range': safe_range
})


def eval_statements(statement, variable_context):
    """Evaluates math statements and returns the value

    args
        statement: a simple python-like math statement
        variable_context: a dict with variable names as key and assigned values as dict values
    """
    # variable values should be numbers
    var_types = set(type(value) for value in variable_context.values())
    if not var_types.issubset({float, Decimal, date, datetime, NoneType, bool}.union(set(six.integer_types))):
        raise InvalidExpression

    evaluator = SimpleEval(operators=SAFE_OPERATORS, names=variable_context, functions=FUNCTIONS)
    return evaluator.eval(statement)


SUM = 'sum'
COUNT = 'count'
MIN = 'min'
MAX = 'max'
FIRST_ITEM = 'first_item'
LAST_ITEM = 'last_item'
SUPPORTED_UCR_AGGREGATIONS = [SUM, COUNT, MIN, MAX, FIRST_ITEM, LAST_ITEM]


def aggregate_items(items, fn_name):

    aggregation_fn_map = {
        SUM: _sum,
        COUNT: _count,
        MIN: _min,
        MAX: _max,
        FIRST_ITEM: _first_item,
        LAST_ITEM: _last_item,
    }

    if not isinstance(items, list):
        return None

    assert fn_name in SUPPORTED_UCR_AGGREGATIONS
    aggregation_fn = aggregation_fn_map[fn_name]
    return aggregation_fn(items)


def _sum(items):
    return _type_safe_agggregate(sum, items)


def _min(items):
    return _type_safe_agggregate(min, items)


def _max(items):
    return _type_safe_agggregate(max, items)


def _type_safe_agggregate(aggregate_fn, items):
    try:
        return aggregate_fn(items)
    except TypeError:
        return None


def _count(items):
    return len(items)


def _first_item(items):
    try:
        return items[0]
    except (IndexError, TypeError):
        return None


def _last_item(items):
    try:
        return items[-1]
    except (IndexError, TypeError):
        return None
