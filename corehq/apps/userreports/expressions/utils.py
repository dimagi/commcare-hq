import copy
import ast
from simpleeval import SimpleEval, DEFAULT_OPERATORS, InvalidExpression


def safe_pow_fn(a, b):
    raise InvalidExpression

SAFE_OPERATORS = copy.copy(DEFAULT_OPERATORS)
SAFE_OPERATORS[ast.Pow] = safe_pow_fn  # don't allow power operations


def eval_statements(statement, variable_context):
    """Evaluates math statements and returns the value

    args
        statement: a simple python-like math statement
        variable_context: a dict with variable names as key and assigned values as dict values
    """
    # variable values should be numbers
    var_types = set(type(value) for value in variable_context.values())
    if not var_types.issubset(set([int, float, long])):
        raise InvalidExpression

    evaluator = SimpleEval(operators=SAFE_OPERATORS, names=variable_context)
    return evaluator.eval(statement)


SUM = 'sum'
COUNT = 'count'
SUPPORTED_UCR_AGGREGATIONS = [SUM, COUNT]


def aggregate_items(items, fn_name):

    aggregation_fn_map = {
        SUM: _sum,
        COUNT: _count,
    }

    if not isinstance(items, list):
        return None

    assert fn_name in SUPPORTED_UCR_AGGREGATIONS
    aggregation_fn = aggregation_fn_map[fn_name]
    return aggregation_fn(items)


def _sum(items):
    try:
        return sum(items)
    except TypeError:
        return None


def _count(items):
    return len(items)
