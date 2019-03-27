from __future__ import absolute_import
from __future__ import unicode_literals
from functools import wraps

import six

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
    if isinstance(input, six.text_type) and isinstance(reference, six.integer_types):
        return True
    elif isinstance(input, six.integer_types) and isinstance(reference, six.text_type):
        return False
    return input > reference


def greater_than_equal(input, reference):
    if isinstance(input, six.text_type) and isinstance(reference, six.integer_types):
        return True
    elif isinstance(input, six.integer_types) and isinstance(reference, six.text_type):
        return False
    return input >= reference


def in_(input, reference):
    return input in reference


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
