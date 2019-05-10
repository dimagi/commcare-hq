from __future__ import absolute_import
from __future__ import unicode_literals


def zip_with_gaps(all_items, some_items, all_items_key=None, some_items_key=None):
    """
    Yields pairs of items from `all_items` and `some_items` where item
    keys match.

    Keys do not need to be unique. Keys in `all_items` must be a
    superset of keys in `some_items`. If key functions are not given,
    items are compared directly. Sequence is important: Items are
    assumed to be sorted.

    >>> long_list = ['Alice', 'Apple', 'Bengal', 'Carrot', 'Daring', 'Danger', 'Dakar', 'Electric']
    >>> short_list = ['Cabernet', 'Daedalus', 'Daimler', 'Dog']
    >>> list(zip_with_gaps(long_list, short_list, lambda x: x[0], lambda x: x[0])) == [
    ...    ('Carrot', 'Cabernet'), ('Daring', 'Daedalus'), ('Danger', 'Daimler'), ('Dakar', 'Dog')
    ... ]
    True

    """
    if all_items_key is None:
        all_items_key = lambda x: x  # noqa: E731
    if some_items_key is None:
        some_items_key = lambda x: x  # noqa: E731

    all_iterable = iter(all_items)
    for s_item in some_items:
        a_item = next(all_iterable)
        while some_items_key(s_item) != all_items_key(a_item):
            a_item = next(all_iterable)
        yield (a_item, s_item)
