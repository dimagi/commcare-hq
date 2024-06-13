import doctest
from decimal import Decimal
from uuid import uuid4

import pytest
from django.test import SimpleTestCase

from nose.tools import assert_equal

from .. import matchers
from ..const import SYSTEM_URI_CASE_ID
from ..matchers import (
    GivenName,
    NegativeIdentifier,
    OrganizationMatcher,
    OrganizationName,
    PatientMatcher,
    PersonMatcher,
    PropertyWeight,
)

JOHN = {'name': [{'given': 'Henry John Colchester'.split()}]}


@pytest.mark.parametrize("resource, candidate, expected", [
    # candidate "H. John" matches patient "Henry John Colchester"
    (JOHN, {'name': [{'given': ['H.', 'John']}]}, True),
    # candidate "John" does not match patient "Henry John Colchester"
    (JOHN, {'name': [{'given': ['John']}]}, False),
    (JOHN, {'name': [{'given': ['Henry']}]}, True),
    (JOHN, {'name': [{'given': ['H.', 'J.', 'C.']}]}, False),
    # candidate "Eric John Marwood" matches "Henry John Colchester"
    (JOHN, {'name': [{'given': ['Eric', 'John', 'Marwood']}]}, True),
])
def test_given_name_method(resource, candidate, expected):
    """
    Test the GivenName ComparisonMethod as used by PersonMatcher
    """
    pw = PropertyWeight('$.name[0].given', Decimal('0.3'), GivenName)
    assert pw in PersonMatcher.property_weights
    method = pw.method

    check_method(method, resource, candidate, expected)


@pytest.mark.parametrize("resource, candidate, expected", [
    ({'name': 'Dimagi'}, {'name': 'Dimagi'}, True),
    ({'name': 'Dimagi'}, {'name': 'DiMaggi'}, True),
    ({'name': 'Dimagi'}, {'name': 'Di Maggi'}, False),
    ({'name': 'Dimagi'}, {'name': 'dimCGI'}, True),
])
def test_organization_name_method(resource, candidate, expected):
    """
    Test the OrganizationName method as used by OrganizationMatcher
    """
    pw = PropertyWeight('$.name', Decimal('0.8'), OrganizationName)
    assert pw in OrganizationMatcher.property_weights
    method = pw.method

    check_method(method, resource, candidate, expected)


def check_method(method, a, b, expected):
    result = method.is_match(a, b)
    assert_equal(result, expected)


@pytest.mark.parametrize("a, b, expected", [
    ('name|Beth Harmon', 'name|Elizabeth Harmon', False),
    ('name|Beth', 'name|Beth', True),
    ('name|Elizabeth Harmon', 'name|Elisabeth Harmon', True),
    ('given_name|Elizabeth', 'family_name|Harmon', True),
])
def test_negative_identifier(a, b, expected):
    result = NegativeIdentifier.compare(a, b)
    assert_equal(result, expected)


class TestPatientCandidates(SimpleTestCase):

    def test_with_commcare_id(self):
        case_id = str(uuid4())
        patient = {
            'id': case_id,
            'name': [{
                'text': 'Beth Harmon',
                'given': ['Elizabeth'],
                'family': 'Harmon',
            }],
            'identifier': [{
                'system': SYSTEM_URI_CASE_ID,
                'value': case_id,
            }]
        }
        candidates = [
            {
                'id': '1',
                'name': [{
                    'given': ['Elizabeth'],
                    'family': 'Harmon',
                }],
                'identifier': [{
                    'system': SYSTEM_URI_CASE_ID,
                    'value': str(uuid4()),
                }],
            },
            {
                'id': '2',
                'name': [{'given': ['Jolene']}],
                'identifier': [{
                    'system': SYSTEM_URI_CASE_ID,
                    'value': case_id,
                }],
            },
            {
                'id': '3',
                'name': [{'family': 'Harmon'}],
                'identifier': [{
                    'system': SYSTEM_URI_CASE_ID,
                    'value': case_id,
                }],
            },
        ]
        matcher = PatientMatcher(patient)
        matches = matcher.find_matches(candidates)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['id'], '3')

        scores = [matcher.get_score(c) for c in candidates]
        expected = [
            Decimal('-0.4'),  # Same name, different ID
            Decimal('0.5'),  # Same ID, different name
            Decimal('1.2'),  # Same ID, same family name
        ]
        self.assertEqual(scores, expected)


def test_doctests():
    results = doctest.testmod(matchers)
    assert_equal(results.failed, 0)
