import doctest
from collections import namedtuple

from testil import eq

from corehq.util import itertools
from corehq.util.itertools import zip_with_gaps


def test_doctests():
    results = doctest.testmod(itertools)
    assert results.failed == 0


def test_zip_with_gaps_key_funcs():
    """
    Specifying a keyfunc should use it to match items
    """
    WithFirstName = namedtuple('WithFirstName', 'username first_name')
    WithLastName = namedtuple('WithLastName', 'username last_name')

    def get_username(dev):
        return dev.username

    devs = [
        ('Biyeun', 'Buczyk', 'biyeun'),
        ('Cory', 'Zue', 'czue'),
        ('Danny', 'Roberts', 'dannyroberts'),
        ('Jenny', 'Schweers', 'orangejenny'),
        ('Nick', 'Pellegrino', 'nickpell'),
        ('Simon', 'Kelly', 'snopoke'),
    ]
    some_first_names = [WithFirstName(usr, fst) for i, (fst, lst, usr)
                        in enumerate(devs) if i < 4]
    all_last_names = [WithLastName(usr, lst) for fst, lst, usr in devs]

    zipped = zip_with_gaps(
        sorted(all_last_names, key=get_username),
        sorted(some_first_names, key=get_username),
        all_items_key=get_username,
        some_items_key=get_username
    )
    names = [(fst.first_name, lst.last_name) for lst, fst in zipped]
    eq(names, [
        ('Biyeun', 'Buczyk'),
        ('Cory', 'Zue'),
        ('Danny', 'Roberts'),
        ('Jenny', 'Schweers'),
    ])


def test_zip_with_gaps_missing_from_all():
    """
    Items missing from `all_items` will be missing from the result
    """
    all_items = [1, 2, 2, 3, 3, 3, 5, 5, 5, 5, 5]
    some_items = [3, 3, 3, 3, 3]
    zipped = zip_with_gaps(all_items, some_items)
    eq(list(zipped), [(3, 3), (3, 3), (3, 3)])


def test_zip_with_gaps_not_in_all():
    """
    Items not found in `all_items` will skip all remaining items.
    """
    all_items = [1, 2, 4]
    some_items = [1, 3, 4]
    zipped = zip_with_gaps(all_items, some_items)
    eq(list(zipped), [(1, 1)])


def test_zip_with_gaps_unsorted():
    """
    Unsorted `some_items` will return the first item from `all_items`
    that matches and drop the skipped items.
    """
    all_items = [1, 2, 3, 4, 5, 6, 7]
    some_items = [6, 7, 3, 4]
    zipped = zip_with_gaps(all_items, some_items)
    eq(list(zipped), [(6, 6), (7, 7)])
