import copy
import ast
from simpleeval import SimpleEval, DEFAULT_OPERATORS, InvalidExpression

from corehq.apps.userreports.exceptions import BadSpecError


def safe_pow_fn(a, b):
    raise InvalidExpression

SAFE_OPERATORS = copy.copy(DEFAULT_OPERATORS)
SAFE_OPERATORS[ast.Pow] = safe_pow_fn  # don't allow power operations


def eval_math_equation(statement, variable_context):
    """

    """
    evaluator = SimpleEval(operators=SAFE_OPERATORS, names=variable_context)
    try:
        return evaluator.eval(statement)
    except InvalidExpression:
        raise BadSpecError
