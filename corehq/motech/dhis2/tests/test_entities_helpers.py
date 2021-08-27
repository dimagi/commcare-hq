import datetime
import doctest
from unittest.mock import Mock, call, patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.domain.shortcuts import create_domain
from corehq.motech.auth import AuthManager
from corehq.motech.dhis2.dhis2_config import (
    Dhis2CaseConfig,
    Dhis2EntityConfig,
    RelationshipConfig,
)
from corehq.motech.dhis2.entities_helpers import (
    create_relationships,
    get_supercase,
    send_dhis2_entities,
    validate_tracked_entity,
)
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.requests import Requests
from corehq.motech.value_source import get_case_trigger_info_for_case

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


def set_up_cases(factory, with_dhis2_id=True):
    child_id = str(uuid4())
    parent_id = str(uuid4())
    child, parent = factory.create_or_update_case(
        CaseStructure(
            case_id=child_id,
            attrs={
                'create': True,
                'case_type': 'child',
                'case_name': 'Johnny APPLESEED',
                'owner_id': 'b0b',
                'external_id': 'johnny12345' if with_dhis2_id else '',
                'update': {
                    'first_name': 'Johnny',
                    'last_name': 'Appleseed',
                    'date_of_birth': '2021-08-27',
                    'dhis2_org_unit_id': 'abcdef12345',
                },
            },
            indices=[CaseIndex(
                CaseStructure(
                    case_id=parent_id,
                    attrs={
                        'create': True,
                        'case_type': 'mother',
                        'case_name': 'Alice APPLESEED',
                        'owner_id': 'b0b',
                        'external_id': 'alice123456' if with_dhis2_id else '',
                        'update': {
                            'first_name': 'Alice',
                            'last_name': 'Appleseed',
                            'dhis2_org_unit_id': 'abcdef12345',
                        },
                    },
                ),
                relationship='child',
                related_type='mother',
                identifier='parent',
            )],
        )
    )
    return child, parent


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
        self.child_case, self.parent_case = set_up_cases(self.factory)

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


class TestCreateRelationships(TestCase):

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
        self.child_case, self.parent_case = set_up_cases(self.factory)
        patcher = patch('corehq.motech.dhis2.entities_helpers.create_relationship')
        self.create_relationship_func = patcher.start()
        self.addCleanup(patcher.stop)
        self.supercase_config = Dhis2CaseConfig.wrap({
            'case_type': 'mother',
            'te_type_id': 'person12345',
            'tei_id': {'case_property': 'external_id'},
            'org_unit_id': {'case_property': 'dhis2_org_unit_id'},
            'attributes': {},
            'form_configs': [],
            'finder_config': {},
        })

    def test_no_relationships(self):
        requests = object()
        case_trigger_info = get_case_trigger_info_for_case(
            self.child_case,
            [{'case_property': 'external_id'}, {'case_property': 'dhis2_org_unit_id'}]
        )
        subcase_config = Dhis2CaseConfig.wrap({
            'case_type': 'child',
            'te_type_id': 'person12345',
            'tei_id': {'case_property': 'external_id'},
            'org_unit_id': {'case_property': 'dhis2_org_unit_id'},
            'attributes': {},
            'form_configs': [],
            'finder_config': {},
            'relationships_to_export': [{
                'identifier': 'parent',
                'referenced_type': 'mother',
                # No DHIS2 relationship types configured
            }]
        })
        dhis2_entity_config = Dhis2EntityConfig(
            case_configs=[subcase_config, self.supercase_config]
        )

        create_relationships(
            requests,
            case_trigger_info,
            subcase_config,
            dhis2_entity_config,
        )
        self.create_relationship_func.assert_not_called()

    def test_one_relationship_given(self):
        requests = object()
        case_trigger_info = get_case_trigger_info_for_case(
            self.child_case,
            [{'case_property': 'external_id'},
             {'case_property': 'dhis2_org_unit_id'}]
        )
        subcase_config = Dhis2CaseConfig.wrap({
            'case_type': 'child',
            'te_type_id': 'person12345',
            'tei_id': {'case_property': 'external_id'},
            'org_unit_id': {'case_property': 'dhis2_org_unit_id'},
            'attributes': {},
            'form_configs': [],
            'finder_config': {},
            'relationships_to_export': [{
                'identifier': 'parent',
                'referenced_type': 'mother',
                'subcase_to_supercase_dhis2_id': 'b2a12345678',
            }]
        })
        dhis2_entity_config = Dhis2EntityConfig(
            case_configs=[subcase_config, self.supercase_config]
        )

        create_relationships(
            requests,
            case_trigger_info,
            subcase_config,
            dhis2_entity_config,
        )
        self.create_relationship_func.assert_called_with(
            requests,
            'b2a12345678',
            'johnny12345',
            'alice123456',
        )

    def test_index_given_twice(self):
        requests = object()
        case_trigger_info = get_case_trigger_info_for_case(
            self.child_case,
            [{'case_property': 'external_id'},
             {'case_property': 'dhis2_org_unit_id'}]
        )
        subcase_config = Dhis2CaseConfig.wrap({
            'case_type': 'child',
            'te_type_id': 'person12345',
            'tei_id': {'case_property': 'external_id'},
            'org_unit_id': {'case_property': 'dhis2_org_unit_id'},
            'attributes': {},
            'form_configs': [],
            'finder_config': {},
            'relationships_to_export': [{
                'identifier': 'parent',
                'referenced_type': 'mother',
                'subcase_to_supercase_dhis2_id': 'b2a12345678',
            }, {
                'identifier': 'parent',
                'referenced_type': 'mother',
                'supercase_to_subcase_dhis2_id': 'a2b12345678',
            }]
        })
        dhis2_entity_config = Dhis2EntityConfig(
            case_configs=[subcase_config, self.supercase_config]
        )

        create_relationships(
            requests,
            case_trigger_info,
            subcase_config,
            dhis2_entity_config,
        )
        self.create_relationship_func.assert_any_call(
            requests,
            'b2a12345678',
            'johnny12345',
            'alice123456',
        )
        self.create_relationship_func.assert_called_with(
            requests,
            'a2b12345678',
            'alice123456',
            'johnny12345',
        )

    def test_both_relationships_given(self):
        requests = object()
        case_trigger_info = get_case_trigger_info_for_case(
            self.child_case,
            [{'case_property': 'external_id'},
             {'case_property': 'dhis2_org_unit_id'}]
        )
        subcase_config = Dhis2CaseConfig.wrap({
            'case_type': 'child',
            'te_type_id': 'person12345',
            'tei_id': {'case_property': 'external_id'},
            'org_unit_id': {'case_property': 'dhis2_org_unit_id'},
            'attributes': {},
            'form_configs': [],
            'finder_config': {},
            'relationships_to_export': [{
                'identifier': 'parent',
                'referenced_type': 'mother',
                'subcase_to_supercase_dhis2_id': 'b2a12345678',
                'supercase_to_subcase_dhis2_id': 'a2b12345678',
            }]
        })
        dhis2_entity_config = Dhis2EntityConfig(
            case_configs=[subcase_config, self.supercase_config]
        )

        create_relationships(
            requests,
            case_trigger_info,
            subcase_config,
            dhis2_entity_config,
        )
        self.create_relationship_func.assert_any_call(
            requests,
            'a2b12345678',
            'alice123456',
            'johnny12345',
        )
        self.create_relationship_func.assert_called_with(
            requests,
            'b2a12345678',
            'johnny12345',
            'alice123456',
        )


class TestRequests(TestCase):

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
        self.child_case, self.parent_case = set_up_cases(
            self.factory,
            with_dhis2_id=False,
        )
        self.supercase_config = Dhis2CaseConfig.wrap({
            'case_type': 'mother',
            'te_type_id': 'person12345',
            'tei_id': {'case_property': 'external_id'},
            'org_unit_id': {'case_property': 'dhis2_org_unit_id'},
            'attributes': {
                'w75KJ2mc4zz': {
                    'case_property': 'first_name'
                },
                'zDhUuAYrxNC': {
                    'case_property': 'last_name'
                }
            },
            'form_configs': [],
            'finder_config': {},
        })
        self.subcase_config = Dhis2CaseConfig.wrap({
            'case_type': 'child',
            'te_type_id': 'person12345',
            'tei_id': {'case_property': 'external_id'},
            'org_unit_id': {'case_property': 'dhis2_org_unit_id'},
            'attributes': {
                'w75KJ2mc4zz': {
                    'case_property': 'first_name'
                },
                'zDhUuAYrxNC': {
                    'case_property': 'last_name'
                },
                'iESIqZ0R0R0': {
                    'case_property': 'date_of_birth'
                }
            },
            'form_configs': [],
            'finder_config': {},
            'relationships_to_export': [{
                'identifier': 'parent',
                'referenced_type': 'mother',
                'subcase_to_supercase_dhis2_id': 'b2a12345678',
                'supercase_to_subcase_dhis2_id': 'a2b12345678',
            }]
        })
        patcher = patch('corehq.motech.requests.Requests.post')
        self.post_func = patcher.start()
        self.addCleanup(patcher.stop)
        self.post_func.side_effect = [
            Response({'response': {'importSummaries': [{'reference': 'ParentTEI12'}]}}),
            Response({'response': {'importSummaries': [{'reference': 'ChildTEI123'}]}}),
            Response({'response': {'imported': 1}}),
            Response({'response': {'imported': 1}}),
        ]

    def test_requests(self):
        repeater = Mock()
        repeater.dhis2_entity_config = Dhis2EntityConfig(
            case_configs=[self.subcase_config, self.supercase_config]
        )
        requests = Requests(
            DOMAIN,
            'https://dhis2.example.com/',
            auth_manager=AuthManager(),
        )
        value_source_configs = [
            {'case_property': 'external_id'},
            {'case_property': 'first_name'},
            {'case_property': 'last_name'},
            {'case_property': 'date_of_birth'},
            {'case_property': 'dhis2_org_unit_id'},
        ]
        case_trigger_infos = [
            get_case_trigger_info_for_case(self.parent_case, value_source_configs),
            get_case_trigger_info_for_case(self.child_case, value_source_configs)
        ]
        send_dhis2_entities(requests, repeater, case_trigger_infos)
        calls = [
            call(
                '/api/trackedEntityInstances/',
                json={
                    'trackedEntityType': 'person12345',
                    'orgUnit': 'abcdef12345',
                    'attributes': [
                        {'attribute': 'w75KJ2mc4zz', 'value': 'Alice'},
                        {'attribute': 'zDhUuAYrxNC', 'value': 'Appleseed'}
                    ]
                },
                raise_for_status=True,
            ),
            call(
                '/api/trackedEntityInstances/',
                json={
                    'trackedEntityType': 'person12345',
                    'orgUnit': 'abcdef12345',
                    'attributes': [
                        {'attribute': 'w75KJ2mc4zz', 'value': 'Johnny'},
                        {'attribute': 'zDhUuAYrxNC', 'value': 'Appleseed'},
                        {'attribute': 'iESIqZ0R0R0', 'value': datetime.date(2021, 8, 27)},
                    ]
                },
                raise_for_status=True,
            ),
            call(
                '/api/relationships/',
                json={
                    'relationshipType': 'a2b12345678',
                    'from': {'trackedEntityInstance': {'trackedEntityInstance': 'ParentTEI12'}},
                    'to': {'trackedEntityInstance': {'trackedEntityInstance': 'ChildTEI123'}},
                },
                raise_for_status=True,
            ),
            call(
                '/api/relationships/',
                json={
                    'relationshipType': 'b2a12345678',
                    'from': {'trackedEntityInstance': {'trackedEntityInstance': 'ChildTEI123'}},
                    'to': {'trackedEntityInstance': {'trackedEntityInstance': 'ParentTEI12'}},
                },
                raise_for_status=True,
            )
        ]
        self.post_func.assert_has_calls(calls)


def test_doctests():
    from corehq.motech.dhis2 import entities_helpers

    results = doctest.testmod(entities_helpers)
    assert results.failed == 0


def are_cases_equal(a, b):  # or at least equal enough for our test
    attrs = ('domain', 'case_id', 'type', 'name', 'owner_id')
    return all(getattr(a, attr) == getattr(b, attr) for attr in attrs)


class Response:

    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data
