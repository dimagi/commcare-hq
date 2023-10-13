import re
from functools import wraps

from corehq.apps.userreports.exceptions import BadSpecError


def equal(input, reference):
    return input == reference


def not_equal(input, reference):
    return input != reference


def in_multiselect(input, reference):
    return reference in (input or '').split(' ')


def any_in_multiselect(input, reference):
    return any([subval in (input or '').split(' ') for subval in reference])


def less_than(input, reference):
    return input < reference


def less_than_equal(input, reference):
    return input <= reference


def greater_than(input, reference):
    if isinstance(input, str) and isinstance(reference, int):
        return True
    elif isinstance(input, int) and isinstance(reference, str):
        return False
    return input > reference


def greater_than_equal(input, reference):
    if isinstance(input, str) and isinstance(reference, int):
        return True
    elif isinstance(input, int) and isinstance(reference, str):
        return False
    return input >= reference


def in_(input, reference):
    return input in reference


def regex_search(input, reference):
    try:
        regex = re.compile(reference)
    except re.error:
        raise BadSpecError(f"Invalid regular expression: {reference}")
    else:
        return bool(re.search(regex, input))


OPERATORS = {
    'eq': equal,
    'not_eq': not_equal,
    'in': in_,
    'in_multi': in_multiselect,
    'any_in_multi': any_in_multiselect,
    'lt': less_than,
    'lte': less_than_equal,
    'gt': greater_than,
    'gte': greater_than_equal,
    'regex': regex_search,
}


OPERATOR_DISPLAY = {
    'equal': '=',
    'not_equal': '!=',
    'in_': 'in',
    'in_multiselect': 'in_multiselect',
    'any_in_multiselect': 'any_in_multiselect',
    'less_than': '<',
    'less_than_equal': '<=',
    'greater_than': '>',
    'greater_than_equal': '>=',
    'regex_search': 'regex_search',
}


def get_operator(slug):
    def _get_safe_operator(fn):
        @wraps(fn)
        def _safe_operator(input, reference):
            try:
                return fn(input, reference)
            except TypeError:
                return False
        return _safe_operator
    try:
        return _get_safe_operator(OPERATORS[slug.lower()])
    except KeyError:
        raise BadSpecError('{0} is not a valid operator. Choices are {1}'.format(
            slug,
            ', '.join(list(OPERATORS)),
        ))
