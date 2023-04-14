import ast
import copy
import operator
from datetime import date, datetime
from decimal import Decimal

from simpleeval import (
    DEFAULT_OPERATORS,
    FeatureNotAvailable,
    InvalidExpression,
    SimpleEval,
)

from corehq.apps.userreports.expressions.evaluator.functions import FUNCTIONS


def safe_pow_fn(a, b):
    raise InvalidExpression


SAFE_TYPES = {float, Decimal, date, datetime, type(None), bool, int, str}

SAFE_OPERATORS = copy.copy(DEFAULT_OPERATORS)
SAFE_OPERATORS[ast.Pow] = safe_pow_fn  # don't allow power operations
SAFE_OPERATORS[ast.Not] = operator.not_


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
