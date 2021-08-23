import doctest
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.domain.shortcuts import create_domain
from corehq.motech.dhis2.dhis2_config import RelationshipConfig
from corehq.motech.dhis2.entities_helpers import (
    get_supercase,
    validate_tracked_entity,
)
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_case_trigger_info_for_case,
)

DOMAIN = 'test-domain'


class ValidateTrackedEntityTests(SimpleTestCase):

    def test_valid(self):
        """
        validate_tracked_entity() should not raise ConfigurationError
        """
        tracked_entity = {
            "orgUnit": "abc123",
            "trackedEntityType": "def456",
        }
        validate_tracked_entity(tracked_entity)

    def test_extra_key(self):
        tracked_entity = {
            "orgUnit": "abc123",
            "trackedEntityType": "def456",
            "hasWensleydale": False
        }
        with self.assertRaises(ConfigurationError):
            validate_tracked_entity(tracked_entity)

    def test_missing_key(self):
        tracked_entity = {
            "trackedEntityType": "def456",
        }
        with self.assertRaises(ConfigurationError):
            validate_tracked_entity(tracked_entity)

    def test_bad_data_type(self):
        tracked_entity = {
            "orgUnit": 0xabc123,
            "trackedEntityType": 0xdef456
        }
        with self.assertRaises(ConfigurationError):
            validate_tracked_entity(tracked_entity)


class TestGetSupercase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.factory = CaseFactory(domain=DOMAIN)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        self.parent_id = str(uuid4())
        self.child_id = str(uuid4())
        self.child_case, self.parent_case = self.factory.create_or_update_case(
            CaseStructure(
                case_id=self.child_id,
                attrs={
                    'create': True,
                    'case_type': 'child',
                    'case_name': 'Johnny APPLESEED',
                    'owner_id': 'b0b',
                },
                indices=[CaseIndex(
                    CaseStructure(
                        case_id=self.parent_id,
                        attrs={
                            'create': True,
                            'case_type': 'mother',
                            'case_name': 'Alice APPLESEED',
                            'owner_id': 'b0b',
                        },
                    ),
                    relationship='child',
                    related_type='mother',
                    identifier='parent',
                )],
            )
        )

    def test_happy_path(self):
        rel_config = RelationshipConfig.wrap({
            'identifier': 'parent',
            'referenced_type': 'mother',
            'relationship': 'child',
        })

        value_source_configs = [{'case_property': 'external_id'}]
        info = get_case_trigger_info_for_case(self.child_case, value_source_configs)
        parent_case = get_supercase(info, rel_config)
        self.assertTrue(are_cases_equal(parent_case, self.parent_case))


def test_doctests():
    from corehq.motech.dhis2 import entities_helpers

    results = doctest.testmod(entities_helpers)
    assert results.failed == 0


def are_cases_equal(a, b):  # or at least equal enough for our test
    attrs = ('domain', 'case_id', 'type', 'name', 'owner_id')
    return all(getattr(a, attr) == getattr(b, attr) for attr in attrs)
