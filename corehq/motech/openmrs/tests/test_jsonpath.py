from __future__ import absolute_import

from __future__ import unicode_literals
import doctest
from operator import gt, ge, eq

from unittest import TestCase
from jsonpath_rw import Child, Fields, Slice, Where, Root

import corehq.motech.openmrs.jsonpath
from corehq.motech.openmrs.jsonpath import Cmp


MENU = [
    {"egg": 1, "bacon": 1},
    {"egg": 1, "sausage": 1, "bacon": 1},
    {"egg": 1, "spam": 1},
    {"egg": 1, "bacon": 1, "spam": 1},
    {"egg": 1, "bacon": 1, "sausage": 1, "spam": 1},
    {"spam": 2, "bacon": 1, "sausage": 1},
    {"spam": 4, "egg": 1, "bacon": 1},
    {"spam": 4, "egg": 1},
    {"spam": 10, "baked beans": 1}
]


class CmpTests(TestCase):
    def test_str(self):
        jsonpath = Cmp(Fields('spam'), gt, 0)
        self.assertEqual(str(jsonpath), 'spam gt 0')

    def test_equal(self):
        jsonpath1 = Cmp(Fields('spam'), gt, 0)
        jsonpath2 = Cmp(Fields('spam'), gt, 0)
        self.assertEqual(jsonpath1, jsonpath2)

    def test_not_equal(self):
        jsonpath1 = Cmp(Fields('spam'), gt, 0)
        jsonpath2 = Cmp(Fields('spam'), ge, 0)
        self.assertNotEqual(jsonpath1, jsonpath2)

    def test_find_one(self):
        max_spam = MENU[-1]
        jsonpath = Cmp(Fields('spam'), gt, 0)  # "spam gt 0"
        values = [match.value for match in jsonpath.find(max_spam)]
        self.assertEqual(values, [10])

    def test_find_many(self):
        jsonpath = Cmp(Child(Slice(), Fields('spam')), gt, 0)  # "[*].spam gt 0"
        self.assertEqual(str(jsonpath), '[*].spam gt 0')
        values = [match.value for match in jsonpath.find(MENU)]
        self.assertEqual(values, [1, 1, 1, 2, 4, 4, 10])

    def test_find_where(self):
        # "([*] where spam ge 2).bacon"
        jsonpath = Child(
            Where(Slice(), Cmp(Fields('spam'), ge, 2)),
            Fields('bacon')
        )
        matches = jsonpath.find(MENU)
        self.assertEqual(len(matches), 2)  # There are two menu items with bacon where spam >= 2

    def test_cmp_list(self):
        jsonpath = Cmp(Root(), eq, 1)  # "[*] eq 1"
        matches = jsonpath.find(MENU)
        self.assertEqual(len(matches), 0)


class DocTests(TestCase):
    def test_doctests(self):
        results = doctest.testmod(corehq.motech.openmrs.jsonpath)
        self.assertEqual(results.failed, 0)
