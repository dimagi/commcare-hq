import inspect
from datetime import date, timedelta
from inspect import Parameter

from jsonpath_ng.ext import parse as jsonpath_parse
from simpleeval import DEFAULT_FUNCTIONS

from corehq.apps.userreports.exceptions import BadSpecError

CONTEXT_PARAM_NAME = "_bound_context"
NEEDS_CONTEXT_PARAM_NAME = "bind_context"


def safe_range(start, *args):
    ret = list(range(start, *args))
    if len(ret) < 100:
        return ret
    return None


def bind_context(fn):
    """Decorator to 'tag' functions as needing the execution context.
    This also validates that the function has the correct keyword argument.
    """
    params = inspect.signature(fn).parameters
    if CONTEXT_PARAM_NAME not in params or params[CONTEXT_PARAM_NAME].kind != Parameter.KEYWORD_ONLY:
        raise Exception(f"Function {fn} must have a keyword only argument called {CONTEXT_PARAM_NAME}")
    setattr(fn, NEEDS_CONTEXT_PARAM_NAME, True)
    return fn


@bind_context
def jsonpath_eval(expr, as_list=False, context=None, *, _bound_context):
    """
    Evaluate a jsonpath expression.

    @param expr: The jsonpath expression.
    @param as_list: When set to True, always return the full list of matches, even if it is emtpy.
                    If set to False then the return value will be `None` if no matches are found.
                    If a single match is found the matched value will be returned.
                    If more than one match is found, they will all be returned as a list.
    @param context: Optional context for evaluation. If not supplied the full context of the evaluator
                    will be used.
    @returns: See `as_list`.
    """
    context = context or _bound_context.names
    try:
        parsed_expr = jsonpath_parse(expr)
    except Exception as e:
        raise BadSpecError(f'Error parsing jsonpath expression <pre>{expr}</pre>. '
                           f'Message is {str(e)}')

    values = [match.value for match in parsed_expr.find(context)]
    if as_list:
        return values

    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return values


@bind_context
def context_eval(*, _bound_context):
    return _bound_context.names


@bind_context
def named_eval(name, context=None, *, _bound_context):
    context = context or _bound_context.names
    return _bound_context.eval_spec({
        "type": "named", "name": name
    }, context)


@bind_context
def root_context(*, _bound_context):
    return _bound_context.root_context


FUNCTIONS = DEFAULT_FUNCTIONS
FUNCTIONS.update({
    'timedelta_to_seconds': lambda x: x.total_seconds() if isinstance(x, timedelta) else None,
    'range': safe_range,
    'today': date.today,
    'days': lambda t: t.days,
    'round': round,
    'context': context_eval,
    'root_context': root_context,
    'jsonpath': jsonpath_eval,
    'named': named_eval,
})
