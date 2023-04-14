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
    DISALLOW_FUNCTIONS,
    FunctionNotDefined,
)

from .functions import FUNCTIONS


def safe_pow_fn(a, b):
    raise InvalidExpression


SAFE_TYPES = {float, Decimal, date, datetime, type(None), bool, int, str, dict, list}

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

        try:
            func = self.functions[node.func.id]
        except KeyError:
            raise FunctionNotDefined(node.func.id, self.expr)
        except AttributeError as e:
            raise FeatureNotAvailable('Lambda Functions not implemented')

        if func in DISALLOW_FUNCTIONS:
            raise FeatureNotAvailable('This function is forbidden')

        if "_bound_context" in node.keywords:
            raise FeatureNotAvailable("Use of reserved keyword is not allowed")

        kwargs = dict(self._eval(k) for k in node.keywords)
        if getattr(func, 'bind_context', False):
            kwargs["_bound_context"] = self.names

        return func(
            *(self._eval(a) for a in node.args),
            **kwargs
        )


def eval_statements(statement, variable_context):
    """Evaluates math statements and returns the value

    args
        statement: a simple python-like math statement
        variable_context: a dict with variable names as key and assigned values as dict values
    """
    var_types = set(type(value) for value in variable_context.values())
    if not var_types.issubset(SAFE_TYPES):
        raise InvalidExpression('Context contains disallowed types')

    evaluator = EvalNoMethods(operators=SAFE_OPERATORS, names=variable_context, functions=FUNCTIONS)
    return evaluator.eval(statement)
