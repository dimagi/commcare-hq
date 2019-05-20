from __future__ import absolute_import
from __future__ import unicode_literals

from django.utils.functional import Promise

from .couch import get_document_or_404
from .view_utils import reverse


def flatten_list(elements):
    return [item for sublist in elements for item in sublist]


def flatten_non_iterable_list(elements):
    # actually iterate over the list and ensure element to avoid conversion of strings to chars
    # ['abc'] => ['a', 'b', 'c']
    items = []
    for element in elements:
        if isinstance(element, list):
            items.extend(flatten_non_iterable_list(element))
        else:
            items.append(element)
    return items


def eval_lazy(value):
    if isinstance(value, Promise):
        value = value._proxy____cast()
    return value


def cmp(a, b):
    """Comparison function for Python 3

    https://stackoverflow.com/a/22490617/10840
    """
    return (a > b) - (a < b)
