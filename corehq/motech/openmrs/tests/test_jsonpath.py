import doctest
from operator import eq, ge, gt
from unittest import TestCase

from jsonpath_rw import Child, Fields, Root, Slice, Union, Where

import corehq.motech.openmrs.jsonpath
from corehq.motech.openmrs.jsonpath import Cmp, WhereNot


class CmpTests(TestCase):

    menu = [
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
        max_spam = self.menu[-1]
        jsonpath = Cmp(Fields('spam'), gt, 0)  # "spam gt 0"
        values = [match.value for match in jsonpath.find(max_spam)]
        self.assertEqual(values, [10])

    def test_find_many(self):
        jsonpath = Cmp(Child(Slice(), Fields('spam')), gt, 0)  # "[*].spam gt 0"
        self.assertEqual(str(jsonpath), '[*].spam gt 0')
        values = [match.value for match in jsonpath.find(self.menu)]
        self.assertEqual(values, [1, 1, 1, 2, 4, 4, 10])

    def test_find_where(self):
        # "([*] where spam ge 2).bacon"
        jsonpath = Child(
            Where(Slice(), Cmp(Fields('spam'), ge, 2)),
            Fields('bacon')
        )
        matches = jsonpath.find(self.menu)
        self.assertEqual(len(matches), 2)  # There are two menu items with bacon where spam >= 2

    def test_cmp_list(self):
        jsonpath = Cmp(Root(), eq, 1)  # "[*] eq 1"
        matches = jsonpath.find(self.menu)
        self.assertEqual(len(matches), 0)


class WhereNotTests(TestCase):

    patient = {
        "display": "GAN203101 - Tara Devi",
        "person": {
            "display": "Tara Devi",
            "attributes": [
                {
                    "display": "caste = janajati",
                    "uuid": "e29c64b2-8978-4d9e-bc1d-8141a5708006",
                    "value": "janajati",
                    "attributeType": {
                        "uuid": "c1f4239f-3f10-11e4-adec-0800271c1b75",
                        "display": "caste"
                    }
                },
                {
                    "display": "General",
                    "uuid": "18aa6e61-38a2-4852-8058-7d37645a4922",
                    "value": {
                        "uuid": "c1fc20ab-3f10-11e4-adec-0800271c1b75",
                        "display": "General"
                    },
                    "attributeType": {
                        "uuid": "c1f455e7-3f10-11e4-adec-0800271c1b75",
                        "display": "class"
                    }
                }
            ]
        }
    }

    def get_jsonpath(self, attr_type_uuid):
        return Union(
            # Simple values: Return value if it has no children.
            # (person.attributes[*] where attributeType.uuid eq attr_type_uuid).(value where not *)
            Child(
                Where(
                    Child(Child(Fields('person'), Fields('attributes')), Slice()),
                    Cmp(Child(Fields('attributeType'), Fields('uuid')), eq, attr_type_uuid)
                ),
                WhereNot(Fields('value'), Fields('*'))
            ),
            # Concept values: Return value.uuid if value.uuid exists:
            # (person.attributes[*] where attributeType.uuid eq attr_type_uuid).value.uuid
            Child(
                Where(
                    Child(Child(Fields('person'), Fields('attributes')), Slice()),
                    Cmp(Child(Fields('attributeType'), Fields('uuid')), eq, attr_type_uuid)
                ),
                Child(Fields('value'), Fields('uuid'))
            )
        )

    def test_where_not(self):
        jsonpath = self.get_jsonpath("c1f4239f-3f10-11e4-adec-0800271c1b75")
        matches = jsonpath.find(self.patient)
        patient_value = matches[0].value
        self.assertEqual(patient_value, "janajati")

    def test_union(self):
        jsonpath = self.get_jsonpath("c1f455e7-3f10-11e4-adec-0800271c1b75")
        matches = jsonpath.find(self.patient)
        patient_value = matches[0].value
        self.assertEqual(patient_value, "c1fc20ab-3f10-11e4-adec-0800271c1b75")


class DocTests(TestCase):
    def test_doctests(self):
        results = doctest.testmod(corehq.motech.openmrs.jsonpath)
        self.assertEqual(results.failed, 0)
