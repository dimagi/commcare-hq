import doctest
from decimal import Decimal

import pytest

import corehq.motech.dhis2.finders
from corehq.motech.dhis2.dhis2_config import Dhis2CaseConfig
from corehq.motech.dhis2.finders import TrackedEntityInstanceFinder
from corehq.motech.value_source import CaseTriggerInfo

GIVEN_NAME_ATTR = 'w75KJ2mc4zz'
FAMILY_NAME_ATTR = 'zDhUuAYrxNC'
DOB_ATTR = 'iESIqZ0R0R0'


def get_case_config():
    # Case configs are stored as JSON after being wrapped, so
    # DecimalProperty values like "weight" and "confidence_margin" are
    # strings. (See ``config_dhis2_entity_repeater()``.)
    return Dhis2CaseConfig.wrap({
        'case_type': 'case',
        'te_type_id': 'nEenWmSyUEp',
        'tei_id': {'case_property': 'dhis2_tei_id'},
        'org_unit_id': {'case_owner_ancestor_location_field': 'dhis_id'},
        'attributes': {
            GIVEN_NAME_ATTR: {'case_property': 'given_name'},
            FAMILY_NAME_ATTR: {'case_property': 'family_name'},
            DOB_ATTR: {'case_property': 'date_of_birth'},
        },
        'finder_config': {
            'property_weights': [
                {'case_property': 'given_name', 'weight': '0.35'},
                {'case_property': 'family_name', 'weight': '0.55'},
                {'case_property': 'date_of_birth', 'weight': '0.1'},
            ],
            'confidence_margin': '0.5',
        },
    }).to_json()


def get_case_trigger_info():
    return CaseTriggerInfo(
        domain='test-domain',
        case_id='abc123',
        extra_fields={
            'given_name': 'Alice',
            'family_name': 'Apple',
            'date_of_birth': '1990-01-01',
        },
    )


def get_candidate(given_name, family_name, date_of_birth):
    return {'attributes': [
        {'attribute': GIVEN_NAME_ATTR, 'value': given_name},
        {'attribute': FAMILY_NAME_ATTR, 'value': family_name},
        {'attribute': DOB_ATTR, 'value': date_of_birth},
    ]}


@pytest.mark.parametrize('candidate, expected', [
    (get_candidate('Alice', 'Apple', '1990-01-01'), Decimal('1')),
    (get_candidate('Alice', 'Apple', '1991-01-01'), Decimal('0.9')),
    (get_candidate('Alice', 'Banana', '1990-01-01'), Decimal('0.45')),
    (get_candidate('Bob', 'Banana', '1991-01-01'), 0),
])
def test_get_score(candidate, expected):
    finder = TrackedEntityInstanceFinder(None, get_case_config())
    score = finder.get_score(candidate, get_case_trigger_info())
    assert score == expected


def test_confidence_margin():
    finder = TrackedEntityInstanceFinder(None, get_case_config())
    assert finder.confidence_margin == Decimal('0.5')
    # Used like this in ``find_tracked_entity_instances()``
    assert 1 + finder.confidence_margin == Decimal('1.5')


def test_doctests():
    results = doctest.testmod(corehq.motech.dhis2.finders)
    assert results.failed == 0
