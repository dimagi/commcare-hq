import doctest
import json
from datetime import datetime
from unittest.mock import Mock, call, patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.models import WebUser
from corehq.motech.auth import AuthManager
from corehq.motech.dhis2 import entities_helpers
from corehq.motech.dhis2.const import DHIS2_DATA_TYPE_DATE, LOCATION_DHIS_ID
from corehq.motech.dhis2.dhis2_config import (
    Dhis2CaseConfig,
    Dhis2EntityConfig,
    RelationshipConfig,
)
from corehq.motech.dhis2.entities_helpers import (
    create_relationships,
    get_programs_by_id,
    get_supercase,
    register_tracked_entity_instance,
    send_dhis2_entities,
    update_tracked_entity_instance,
    validate_tracked_entity,
)
from corehq.motech.dhis2.exceptions import Dhis2Exception
from corehq.motech.dhis2.forms import Dhis2ConfigForm
from corehq.motech.dhis2.repeaters import Dhis2EntityRepeater, Dhis2Repeater
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.models import ConnectionSettings
from corehq.motech.requests import Requests
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_case_trigger_info_for_case,
    get_form_question_values,
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


class TestDhis2EntitiesHelpers(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(DOMAIN)
        location_type = LocationType.objects.create(
            domain=DOMAIN,
            name='test_location_type',
        )
        cls.location = SQLLocation.objects.create(
            domain=DOMAIN,
            name='test location',
            location_id='test_location',
            location_type=location_type,
            latitude='-33.6543',
            longitude='19.1234',
            metadata={LOCATION_DHIS_ID: "dhis2_location_id"},
        )
        cls.user = WebUser.create(DOMAIN, 'test', 'passwordtest', None, None)
        cls.user.set_location(DOMAIN, cls.location)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(DOMAIN, deleted_by=None)
        cls.location.delete()
        cls.domain.delete()
        super().tearDownClass()

    def test_get_programs_by_id(self):
        program_id = 'test program'

        form = {
            "domain": DOMAIN,
            "form": {
                "@xmlns": "test_xmlns",
                "event_date": "2017-05-25T21:06:27.012000",
                "completed_date": "2017-05-25T21:06:27.012000",
                "event_location": "-33.6543213 19.12344312 abcdefg",
                "name": "test event",
                "meta": {
                    "location": 'test location',
                    "timeEnd": "2017-05-25T21:06:27.012000",
                    "timeStart": "2017-05-25T21:06:17.739000",
                    "userID": self.user.user_id,
                    "username": self.user.username
                }
            },
            "received_on": "2017-05-26T09:17:23.692083Z",
        }
        config = {
            'form_configs': json.dumps([{
                'xmlns': 'test_xmlns',
                'program_id': program_id,
                'event_status': 'COMPLETED',
                'event_location': {
                    'form_question': '/data/event_location'
                },
                'completed_date': {
                    'doc_type': 'FormQuestion',
                    'form_question': '/data/completed_date',
                    'external_data_type': DHIS2_DATA_TYPE_DATE
                },
                'org_unit_id': {
                    'doc_type': 'FormUserAncestorLocationField',
                    'form_user_ancestor_location_field': LOCATION_DHIS_ID
                },
                'datavalue_maps': [
                    {
                        'data_element_id': 'dhis2_element_id',
                        'value': {
                            'doc_type': 'FormQuestion',
                            'form_question': '/data/name'
                        }
                    }
                ]
            }])
        }
        config_form = Dhis2ConfigForm(data=config)
        self.assertTrue(config_form.is_valid())
        data = config_form.cleaned_data
        repeater = Dhis2Repeater(domain=DOMAIN)
        conn = ConnectionSettings(domain=DOMAIN, url="http://dummy.com")
        conn.save()
        repeater.dhis2_config['form_configs'] = data['form_configs']
        repeater.connection_settings_id = conn.id
        repeater.save()

        info = CaseTriggerInfo(
            domain=DOMAIN,
            case_id=None,
            owner_id='test_location',
            form_question_values=get_form_question_values(form),
        )

        programs = get_programs_by_id(info, repeater.dhis2_config)

        self.assertDictEqual(
            programs[program_id]['geometry'],
            {'type': 'Point', 'coordinates': [-33.6543, 19.1234]}
        )


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
        ).to_json()

        create_relationships(
            requests,
            case_trigger_info,
            subcase_config,
            dhis2_entity_config,
            []
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
        ).to_json()

        create_relationships(
            requests,
            case_trigger_info,
            subcase_config,
            dhis2_entity_config,
            []
        )
        self.create_relationship_func.assert_called_with(
            requests,
            entities_helpers.RelationshipSpec(
                relationship_type_id='b2a12345678',
                from_tracked_entity_instance_id='johnny12345',
                to_tracked_entity_instance_id='alice123456'
            )
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
        ).to_json()

        create_relationships(
            requests,
            case_trigger_info,
            subcase_config,
            dhis2_entity_config,
            []
        )
        self.create_relationship_func.assert_any_call(
            requests,
            entities_helpers.RelationshipSpec(
                relationship_type_id='b2a12345678',
                from_tracked_entity_instance_id='johnny12345',
                to_tracked_entity_instance_id='alice123456'
            )
        )
        self.create_relationship_func.assert_called_with(
            requests,
            entities_helpers.RelationshipSpec(
                relationship_type_id='a2b12345678',
                from_tracked_entity_instance_id='alice123456',
                to_tracked_entity_instance_id='johnny12345'
            )
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
            []
        )
        self.create_relationship_func.assert_any_call(
            requests,
            entities_helpers.RelationshipSpec(
                relationship_type_id='a2b12345678',
                from_tracked_entity_instance_id='alice123456',
                to_tracked_entity_instance_id='johnny12345'
            )
        )
        self.create_relationship_func.assert_called_with(
            requests,
            entities_helpers.RelationshipSpec(
                relationship_type_id='b2a12345678',
                from_tracked_entity_instance_id='johnny12345',
                to_tracked_entity_instance_id='alice123456'
            )
        )

    def test_existing_relationship_not_created_again(self):
        """Test that we don't try to create a relationship that already exists"""
        requests = object()
        case_trigger_info = get_case_trigger_info_for_case(
            self.child_case, [{
                'case_property': 'external_id'
            }, {
                'case_property': 'dhis2_org_unit_id'
            }]
        )
        subcase_config = Dhis2CaseConfig.wrap({
            'case_type':
                'child',
            'te_type_id':
                'person12345',
            'tei_id': {
                'case_property': 'external_id'
            },
            'org_unit_id': {
                'case_property': 'dhis2_org_unit_id'
            },
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
        dhis2_entity_config = Dhis2EntityConfig(case_configs=[subcase_config, self.supercase_config])
        # Set up a pre-existing relationship which we received from DHIS2
        tracked_entity_relationship_specs = [
            entities_helpers.RelationshipSpec(
                relationship_type_id="b2a12345678",
                from_tracked_entity_instance_id="johnny12345",
                to_tracked_entity_instance_id="alice123456"
            )
        ]

        create_relationships(
            requests,
            case_trigger_info,
            subcase_config,
            dhis2_entity_config,
            tracked_entity_relationship_specs
        )

        # Only once of the two relationships should trigger a call to create, since the other already exists
        self.create_relationship_func.assert_called_once()
        # Ensure that the correct relationship triggered a create call
        _requests, relationship_created = self.create_relationship_func.call_args[0]
        existing_relationship = tracked_entity_relationship_specs[0]
        assert relationship_created.relationship_type_id != existing_relationship.relationship_type_id


class TestRegisterTrackedEntityInstance(TestCase):
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
        build_patch = patch('corehq.motech.dhis2.entities_helpers._build_tracked_entity')
        self.build_func = build_patch.start()
        self.addCleanup(build_patch.stop)
        self.build_func.return_value = [{'trackedEntityInstance': 'foobar'}, None]

        post_patch = patch('corehq.motech.requests.Requests.post')
        self.post_func = post_patch.start()
        self.addCleanup(post_patch.stop)
        self.post_func.return_value = Mock(
            status_code=200,
            json=lambda: {
                'response': {
                    'importSummaries': ['foobar'],
                    'enrollments': {
                        'importSummaries': [
                            {
                                'events': {
                                    'importSummaries': [
                                        {
                                            'status': 'ERROR',
                                            'description': 'foobar error'
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                }
            },
        )

    def test_register_tracked_entity_instance_errors(self):
        requests = Requests(
            DOMAIN,
            'https://dhis2.example.com/',
            auth_manager=AuthManager(),
        )
        case_trigger_info = CaseTriggerInfo(domain=DOMAIN, case_id=None)
        case_config = {
            'te_type_id': 'foobar',
            'org_unit_id': {
                'doc_type': 'CaseOwnerAncestorLocationField',
                'location_field': 'dhis_id'
            },
            'tei_id': 'foobar'
        }

        with self.assertRaises(Dhis2Exception):
            register_tracked_entity_instance(requests, case_trigger_info, case_config)


class TestUpdateTrackedEntityInstance(TestCase):
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
        build_patch = patch('corehq.motech.dhis2.entities_helpers._build_tracked_entity')
        self.build_func = build_patch.start()
        self.addCleanup(build_patch.stop)
        self.build_func.return_value = [{"trackedEntityInstance": "foobar"}, None]

        put_patch = patch('corehq.motech.requests.Requests.put')
        self.put_func = put_patch.start()
        self.addCleanup(put_patch.stop)
        self.put_func.return_value = Mock(
            status_code=200,
            json=lambda: {
                "enrollments": {
                    "importSummaries": [
                        {
                            "events": {
                                "importSummaries": [
                                    {
                                        "status": "ERROR",
                                        "description": "Foobar"
                                    }
                                ]
                            }
                        }
                    ]
                }
            },
        )

    def test_update_tracked_entity_instance_errors(self):
        requests = Requests(
            DOMAIN,
            'https://dhis2.example.com/',
            auth_manager=AuthManager(),
        )

        with self.assertRaises(Dhis2Exception):
            update_tracked_entity_instance(requests, None, None, None, None)


class TestNothingToSend(TestCase):

    def setUp(self):
        self.conn = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='Example DHIS2 server',
            url='https://dhis2.example.com/',
        )

    def tearDown(self):
        self.conn.delete()

    def test_204_response(self):
        repeater = Dhis2EntityRepeater(
            domain=DOMAIN,
            connection_settings_id=self.conn.id,
            dhis2_entity_config={'case_configs': []},
            dhis2_version='2.39.1.1',
            dhis2_version_last_modified=datetime.utcnow(),
        )
        repeat_record = Mock(payload_id='abc123')
        payload = {'form': {}}

        result = repeater.send_request(repeat_record, payload)
        self.assertEqual(result.status_code, 204)
        self.assertEqual(result.reason, 'No content')


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
        ).to_json()
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
                        {'attribute': 'iESIqZ0R0R0', 'value': '2021-08-27'},
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


def test_doctests():
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
