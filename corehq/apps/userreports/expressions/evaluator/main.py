import ast
import copy
import operator
from datetime import date, datetime, timedelta
from decimal import Decimal

from simpleeval import (
    DEFAULT_FUNCTIONS,
    DEFAULT_OPERATORS,
    FeatureNotAvailable,
    InvalidExpression,
    SimpleEval,
)


def safe_pow_fn(a, b):
    raise InvalidExpression


def safe_range(start, *args):
    ret = list(range(start, *args))
    if len(ret) < 100:
        return ret
    return None


SAFE_TYPES = {float, Decimal, date, datetime, type(None), bool, int, str}

SAFE_OPERATORS = copy.copy(DEFAULT_OPERATORS)
SAFE_OPERATORS[ast.Pow] = safe_pow_fn  # don't allow power operations
SAFE_OPERATORS[ast.Not] = operator.not_

FUNCTIONS = DEFAULT_FUNCTIONS
FUNCTIONS.update({
    'timedelta_to_seconds': lambda x: x.total_seconds() if isinstance(x, timedelta) else None,
    'range': safe_range,
    'today': date.today,
    'days': lambda t: t.days,
    'round': round
})


class EvalNoMethods(SimpleEval):
    """Disallow method calls. No real reason for this except that it gives
    users less options to do crazy things that might get them / us into
    hard to back out of situations."""
    def _eval_call(self, node):
        if isinstance(node.func, ast.Attribute):
            raise FeatureNotAvailable("Method calls not allowed.")
        return super(EvalNoMethods, self)._eval_call(node)


def eval_statements(statement, variable_context):
    """Evaluates math statements and returns the value

    args
        statement: a simple python-like math statement
        variable_context: a dict with variable names as key and assigned values as dict values
    """
    # variable values should be numbers
    var_types = set(type(value) for value in variable_context.values())
    if not var_types.issubset(SAFE_TYPES):
        raise InvalidExpression('Context contains disallowed types')

    evaluator = EvalNoMethods(operators=SAFE_OPERATORS, names=variable_context, functions=FUNCTIONS)
    return evaluator.eval(statement)
