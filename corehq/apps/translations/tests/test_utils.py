from __future__ import absolute_import
from __future__ import unicode_literals

import doctest
from collections import namedtuple

from testil import eq

from corehq.apps.translations import utils
from corehq.apps.translations.utils import zip_with_gaps


def test_doctests():
    results = doctest.testmod(utils)
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
    some_first_names = [WithFirstName(u, f) for i, (f, l, u) in enumerate(devs) if i < 4]
    all_last_names = [WithLastName(u, l) for f, l, u in devs]

    zipped = zip_with_gaps(
        sorted(all_last_names, key=get_username),
        sorted(some_first_names, key=get_username),
        all_items_key=get_username,
        some_items_key=get_username
    )
    names = [(f.first_name, l.last_name) for l, f in zipped]
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
