from datetime import date, timedelta

from simpleeval import DEFAULT_FUNCTIONS


def safe_range(start, *args):
    ret = list(range(start, *args))
    if len(ret) < 100:
        return ret
    return None


def bind_context(fn):
    fn.bind_context = True
    return fn


@bind_context
def jsonpath_eval(expr, context=None, *, _bound_context):
    context = context or _bound_context
    from jsonpath_ng.ext import parse as jsonpath_parse
    values = [match.value for match in jsonpath_parse(expr).find(context)]
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return values


@bind_context
def context_eval(*, _bound_context):
    return _bound_context


FUNCTIONS = DEFAULT_FUNCTIONS
FUNCTIONS.update({
    'timedelta_to_seconds': lambda x: x.total_seconds() if isinstance(x, timedelta) else None,
    'range': safe_range,
    'today': date.today,
    'days': lambda t: t.days,
    'round': round,
    'context': context_eval,
    'jsonpath': jsonpath_eval,
})
