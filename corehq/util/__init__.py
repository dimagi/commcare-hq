from .couch import get_document_or_404
from .view_utils import reverse


def remove_dups(list_of_dicts, unique_key):
    keys = set([])
    ret = []
    for d in list_of_dicts:
        if d.get(unique_key) not in keys:
            keys.add(d.get(unique_key))
            ret.append(d)
    return ret


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
