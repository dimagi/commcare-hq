from __future__ import absolute_import, unicode_literals

import doctest

from django.test import SimpleTestCase

from nose.tools import assert_false

from corehq.motech.openmrs import finders_utils
from corehq.motech.openmrs.const import OPENMRS_DATA_TYPE_BOOLEAN
from corehq.motech.openmrs.finders import (
    PatientFinder,
    WeightedPropertyPatientFinder,
    constant_false,
)
from corehq.motech.openmrs.openmrs_config import (
    OpenmrsCaseConfig,
    get_property_map,
)
from corehq.motech.value_source import ConstantString


PATIENT = {
    'uuid': '94c0e9c0-1bea-4467-b3c3-823e36c5adf5',
    'display': '04141401/16/0297 - Mahapajapati Gotami',
    'identifiers': [{
        'identifier': '04141401/16/0297',
        'identifierType': {'uuid': 'e2b97b70-1d5f-11e0-b929-000c29ad1d07', 'display': 'NID'}
    }],
    'person': {
        'gender': 'F',
        'birthdate': '1984-01-01T00:00:00.000+0200',
        'preferredName': {
            'givenName': 'Mahapajapati',
            'familyName': 'Gotami',
        },
        'preferredAddress': {
            'address1': '56 Barnet Street',
            'address2': 'Gardens',
        },
        'attributes': [
            {
                # caste: Buddhist
                'attributeType': {'uuid': 'c1f4239f-3f10-11e4-adec-0800271c1b75'},
                'value': 'Buddhist',
            },
            {
                # class: sc
                'attributeType': {'uuid': 'c1f455e7-3f10-11e4-adec-0800271c1b75'},
                'value': 'c1fcd1c6-3f10-11e4-adec-0800271c1b75',
            }
        ]
    }
}


class CaseMock(dict):
    def get_case_property(self, prop):
        return self[prop]


class PatientFinderTests(SimpleTestCase):
    """
    Tests PatientFinder.wrap()
    """

    def test_wrap_subclass(self):
        """
        PatientFinder.wrap() should return the type of subclass determined by "doc_type"
        """
        finder = PatientFinder.wrap({
            'doc_type': 'WeightedPropertyPatientFinder',
            'searchable_properties': [],
            'property_weights': [],
        })
        self.assertIsInstance(finder, WeightedPropertyPatientFinder)

    def test_create_missing_default(self):
        """
        PatientFinder.create_missing should default to false
        """
        finder = PatientFinder.wrap({
            'doc_type': 'WeightedPropertyPatientFinder',
            'searchable_properties': [],
            'property_weights': [],
        })
        self.assertEqual(
            finder.create_missing,
            ConstantString(
                external_data_type=OPENMRS_DATA_TYPE_BOOLEAN,
                commcare_data_type=None,
                direction=None,
                doc_type='ConstantString',
                value='False',
            )
        )

    def test_create_missing_true(self):
        finder = PatientFinder.wrap({
            'doc_type': 'WeightedPropertyPatientFinder',
            'searchable_properties': [],
            'property_weights': [],
            'create_missing': True,
        })
        self.assertEqual(
            finder.create_missing,
            ConstantString(
                external_data_type=OPENMRS_DATA_TYPE_BOOLEAN,
                commcare_data_type=None,
                direction=None,
                doc_type='ConstantString',
                value='True',
            )
        )

    def test_create_missing_false(self):
        finder = PatientFinder.wrap({
            'doc_type': 'WeightedPropertyPatientFinder',
            'searchable_properties': [],
            'property_weights': [],
            'create_missing': False,
        })
        self.assertEqual(
            finder.create_missing,
            ConstantString(
                external_data_type=OPENMRS_DATA_TYPE_BOOLEAN,
                commcare_data_type=None,
                direction=None,
                doc_type='ConstantString',
                value='False',
            )
        )


def test_constant_false():
    info = {}
    assert_false(constant_false.get_value(info))


class WeightedPropertyPatientFinderTests(SimpleTestCase):
    """
    Tests get_property_map() for WeightedPropertyPatientFinder.
    """

    def setUp(self):
        self.case_config = OpenmrsCaseConfig.wrap({
            'patient_identifiers': {
                'uuid': {'doc_type': 'CaseProperty', 'case_property': 'openmrs_uuid'},
                'e2b97b70-1d5f-11e0-b929-000c29ad1d07': {'doc_type': 'CaseProperty', 'case_property': 'nid'}
            },
            'match_on_ids': ['uuid'],
            'person_properties': {
                'gender': {'doc_type': 'CaseProperty', 'case_property': 'sex'},
                'birthdate': {'doc_type': 'CaseProperty', 'case_property': 'dob'},
            },
            'person_preferred_name': {
                'givenName': {'doc_type': 'CaseProperty', 'case_property': 'first_name'},
                'familyName': {'doc_type': 'CaseProperty', 'case_property': 'last_name'},
            },
            'person_preferred_address': {
                'address1': {'doc_type': 'CaseProperty', 'case_property': 'address_1'},
                'address2': {'doc_type': 'CaseProperty', 'case_property': 'address_2'},
            },
            'person_attributes': {
                'c1f4239f-3f10-11e4-adec-0800271c1b75': {'doc_type': 'CaseProperty', 'case_property': 'caste'},
                'c1f455e7-3f10-11e4-adec-0800271c1b75': {
                    'doc_type': 'CasePropertyMap',
                    'case_property': 'class',
                    'value_map': {
                        'sc': 'c1fcd1c6-3f10-11e4-adec-0800271c1b75',
                        'general': 'c1fc20ab-3f10-11e4-adec-0800271c1b75',
                        'obc': 'c1fb51cc-3f10-11e4-adec-0800271c1b75',
                        'other_caste': 'c207073d-3f10-11e4-adec-0800271c1b75',
                        'st': 'c20478b6-3f10-11e4-adec-0800271c1b75'
                    }
                },
            },
        })
        self.finder = WeightedPropertyPatientFinder.wrap({
            'doc_type': 'WeightedPropertyPatientFinder',
            'searchable_properties': ['last_name'],
            'property_weights': [
                {
                    "case_property": "first_name",
                    "weight": 0.45,
                    "match_type": "levenshtein",
                    "match_params": [0.2]
                },
                {"case_property": "last_name", "weight": 0.45},
                {
                    "case_property": "dob",
                    "weight": 0.2,
                    "match_type": "days_diff",
                    "match_params": [364]
                },
                {"case_property": "address_2", "weight": 0.2},
            ],
        })
        self.finder._property_map = get_property_map(self.case_config)

    def test_person_properties_jsonpath(self):
        for prop in ('sex', 'dob'):
            jsonpath, _ = self.finder._property_map[prop]
            matches = jsonpath.find(PATIENT)
            self.assertEqual(len(matches), 1,
                             'jsonpath "{}" did not uniquely match a patient value'.format(jsonpath))
            patient_value = matches[0].value
            self.assertEqual(patient_value, {
                'sex': 'F',
                'dob': '1984-01-01T00:00:00.000+0200',
            }[prop])

    def test_person_preferred_name_jsonpath(self):
        for prop in ('first_name', 'last_name'):
            jsonpath, _ = self.finder._property_map[prop]
            matches = jsonpath.find(PATIENT)
            self.assertEqual(len(matches), 1,
                             'jsonpath "{}" did not uniquely match a patient value'.format(jsonpath))
            patient_value = matches[0].value
            self.assertEqual(patient_value, {
                'first_name': 'Mahapajapati',
                'last_name': 'Gotami',
            }[prop])

    def test_person_preferred_address_jsonpath(self):
        for prop in ('address_1', 'address_2'):
            jsonpath, _ = self.finder._property_map[prop]
            matches = jsonpath.find(PATIENT)
            self.assertEqual(len(matches), 1,
                             'jsonpath "{}" did not uniquely match a patient value'.format(jsonpath))
            patient_value = matches[0].value
            self.assertEqual(patient_value, {
                'address_1': '56 Barnet Street',
                'address_2': 'Gardens',
            }[prop])

    def test_person_attributes_jsonpath(self):
        for prop in ('caste', 'class'):
            jsonpath, _ = self.finder._property_map[prop]
            matches = jsonpath.find(PATIENT)
            self.assertEqual(len(matches), 1,
                             'jsonpath "{}" did not uniquely match a patient value'.format(jsonpath))
            patient_value = matches[0].value
            self.assertEqual(patient_value, {
                'caste': 'Buddhist',
                'class': 'c1fcd1c6-3f10-11e4-adec-0800271c1b75',
            }[prop])

    def test_patient_identifiers_jsonpath(self):
        for prop in ('openmrs_uuid', 'nid'):
            jsonpath, _ = self.finder._property_map[prop]
            matches = jsonpath.find(PATIENT)
            self.assertEqual(len(matches), 1,
                             'jsonpath "{}" did not uniquely match a patient value'.format(jsonpath))
            patient_value = matches[0].value
            self.assertEqual(patient_value, {
                'openmrs_uuid': '94c0e9c0-1bea-4467-b3c3-823e36c5adf5',
                'nid': '04141401/16/0297',
            }[prop])

    def test_get_score_ge_1(self):
        case = CaseMock({
            'first_name': 'Mapajapati',
            'last_name': 'Gotami',
            'address_1': '56 Barnet Street',
            'address_2': 'Gardens',
            'dob': '1984-12-03T00:00:00.000-0400',
        })
        score = self.finder.get_score(PATIENT, case)
        self.assertGreaterEqual(score, 1)

    def test_get_score_lt_1(self):
        case = CaseMock({
            'first_name': 'Mahapajapati',
            'last_name': 'Gotami',
            'address_1': '585 Massachusetts Ave',
            'address_2': 'Cambridge',
            'dob': '1983-01-01T00:00:00.000+0200',
        })
        score = self.finder.get_score(PATIENT, case)
        self.assertLess(score, 1)


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(finders_utils)
        self.assertEqual(results.failed, 0)
