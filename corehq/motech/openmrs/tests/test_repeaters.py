from __future__ import absolute_import, unicode_literals

import copy
import doctest
import json
import os
import uuid
import warnings

from django.test import SimpleTestCase, TestCase

import mock

from casexml.apps.case.models import CommCareCase

import corehq.motech.openmrs.repeater_helpers
from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import XFormInstanceSQL
from corehq.motech.const import DIRECTION_EXPORT, DIRECTION_IMPORT
from corehq.motech.openmrs.const import (
    LOCATION_OPENMRS_UUID,
    OPENMRS_DATA_TYPE_BOOLEAN,
    XMLNS_OPENMRS,
)
from corehq.motech.openmrs.openmrs_config import (
    OpenmrsCaseConfig,
    OpenmrsConfig,
)
from corehq.motech.openmrs.repeater_helpers import (
    create_patient,
    find_or_create_patient,
    get_ancestor_location_openmrs_uuid,
    get_case_location,
    get_case_location_ancestor_repeaters,
    get_patient_by_identifier,
    get_patient_by_uuid,
    get_relevant_case_updates_from_form_json,
    save_match_ids,
)
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.motech.value_source import (
    CaseTriggerInfo,
    get_form_question_values,
)
from corehq.util.test_utils import TestFileMixin, _create_case


DOMAIN = 'openmrs-repeater-tests'
PATIENT_SEARCH_RESPONSE = json.loads("""{
    "results": [
        {
            "auditInfo": "REDACTED",
            "display": "REDACTED",
            "identifiers": [
                {
                    "display": "REDACTED",
                    "identifier": "00000000/00/0000",
                    "identifierType": {
                        "display": "REDACTED",
                        "links": "REDACTED",
                        "uuid": "e2b966d0-1d5f-11e0-b929-000c29ad1d07"
                    },
                    "links": "REDACTED",
                    "location": "REDACTED",
                    "preferred": true,
                    "resourceVersion": "1.8",
                    "uuid": "ee1df764-2c2e-4e58-aa4a-1e07bd41301f",
                    "voided": false
                }
            ],
            "links": "REDACTED",
            "person": "REDACTED",
            "resourceVersion": "1.8",
            "uuid": "672c4a51-abad-4b5e-950c-10bc262c9c1a",
            "voided": false
        },
        {
            "auditInfo": "REDACTED",
            "display": "REDACTED",
            "identifiers": [
                {
                    "display": "REDACTED",
                    "identifier": "11111111/11/1111",
                    "identifierType": {
                        "display": "REDACTED",
                        "links": "REDACTED",
                        "uuid": "e2b966d0-1d5f-11e0-b929-000c29ad1d07"
                    },
                    "links": "REDACTED",
                    "location": "REDACTED",
                    "preferred": true,
                    "resourceVersion": "1.8",
                    "uuid": "648254a4-3a13-4e50-b315-e943bd87b58b",
                    "voided": false
                }
            ],
            "links": "REDACTED",
            "person": "REDACTED",
            "resourceVersion": "1.8",
            "uuid": "5ba94fa2-9cb3-4ae6-b400-7bf45783dcbf",
            "voided": false
        }
    ]
}""")
CASE_CONFIG = {
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
}


@mock.patch.object(CaseAccessors, 'get_cases', lambda self, case_ids, ordered=False: [{
    '65e55473-e83b-4d78-9dde-eaf949758997': CommCareCase(
        case_id='65e55473-e83b-4d78-9dde-eaf949758997',
        type='paciente',
        name='Elsa',
        estado_tarv='1',
        tb='0',
    )
}[case_id] for case_id in case_ids])
class OpenmrsRepeaterTest(SimpleTestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_get_case_updates_for_registration(self):
        """
        get_relevant_case_updates_from_form_json should fetch case
        updates from teh given form JSON
        """
        self.assertEqual(
            get_relevant_case_updates_from_form_json(
                'openmrs-repeater-test',
                self.get_json('registration'),
                case_types=['paciente'],
                extra_fields=[]
            ),
            [
                CaseTriggerInfo(
                    case_id='65e55473-e83b-4d78-9dde-eaf949758997',
                    updates={
                        'case_name': 'Elsa',
                        'case_type': 'paciente',
                        'estado_tarv': '1',
                        'owner_id': '9393007a6921eecd4a9f20eefb5c7a8e',
                        'tb': '0',
                    },
                    created=True,
                    closed=False,
                    extra_fields={},
                    form_question_values={},
                )
            ]
        )

    def test_get_case_updates_for_followup(self):
        """
        Specifying `extra_fields` should fetch the current value from
        the case
        """
        self.assertEqual(
            get_relevant_case_updates_from_form_json(
                'openmrs-repeater-test',
                self.get_json('followup'),
                case_types=['paciente'],
                extra_fields=['name', 'estado_tarv', 'tb', 'bandersnatch'],
            ),
            [
                CaseTriggerInfo(
                    case_id='65e55473-e83b-4d78-9dde-eaf949758997',
                    updates={
                        'estado_tarv': '1',
                        'tb': '1',
                    },
                    created=False,
                    closed=False,
                    extra_fields={
                        'name': 'Elsa',
                        'estado_tarv': '1',
                        'tb': '0',
                        'bandersnatch': None,
                    },
                    form_question_values={},
                )
            ]
        )


class GetPatientByUuidTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(GetPatientByUuidTests, cls).setUpClass()
        cls.patient = {
            'uuid': 'c83d9989-585f-4db3-bf55-ca1d0ee7c0af',
            'display': 'Luis Safiana Bassilo'
        }
        response = mock.Mock()
        response.json.return_value = cls.patient
        cls.requests = mock.Mock()
        cls.requests.get.return_value = response

    def test_none(self):
        patient = get_patient_by_uuid(self.requests, uuid=None)
        self.assertIsNone(patient)

    def test_empty(self):
        patient = get_patient_by_uuid(self.requests, uuid='')
        self.assertIsNone(patient)

    def test_invalid_uuid(self):
        with self.assertRaises(ValueError):
            # OpenMRS UUIDs have "-" separators
            get_patient_by_uuid(self.requests, uuid='c83d9989585f4db3bf55ca1d0ee7c0af')

    def test_valid_uuid(self):
        patient = get_patient_by_uuid(self.requests, uuid='c83d9989-585f-4db3-bf55-ca1d0ee7c0af')
        self.assertEqual(patient, self.patient)


class GetFormQuestionValuesTests(SimpleTestCase):

    def test_unicode_answer(self):
        value = get_form_question_values({'form': {'foo': {'bar': 'b\u0105z'}}})
        self.assertEqual(value, {'/data/foo/bar': 'b\u0105z'})

    def test_utf8_answer(self):
        value = get_form_question_values({'form': {'foo': {'bar': b'b\xc4\x85z'}}})
        self.assertEqual(value, {'/data/foo/bar': b'b\xc4\x85z'})

    def test_unicode_question(self):
        value = get_form_question_values({'form': {'foo': {'b\u0105r': 'baz'}}})
        self.assertEqual(value, {'/data/foo/b\u0105r': 'baz'})

    def test_utf8_question(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UnicodeWarning)
            value = get_form_question_values({'form': {'foo': {b'b\xc4\x85r': 'baz'}}})
        self.assertEqual(value, {'/data/foo/b\u0105r': 'baz'})

    def test_received_on(self):
        value = get_form_question_values({
            'form': {
                'foo': {'bar': 'baz'},
            },
            'received_on': '2018-11-06T18:30:00.000000Z',
        })
        self.assertDictEqual(value, {
            '/data/foo/bar': 'baz',
            '/metadata/received_on': '2018-11-06T18:30:00.000000Z',
        })

    def test_metadata(self):
        value = get_form_question_values({
            'form': {
                'foo': {'bar': 'baz'},
                'meta': {
                    'timeStart': '2018-11-06T18:00:00.000000Z',
                    'timeEnd': '2018-11-06T18:15:00.000000Z',
                    'spam': 'ham',
                },
            },
            'received_on': '2018-11-06T18:30:00.000000Z',
        })
        self.assertDictEqual(value, {
            '/data/foo/bar': 'baz',
            '/metadata/timeStart': '2018-11-06T18:00:00.000000Z',
            '/metadata/timeEnd': '2018-11-06T18:15:00.000000Z',
            '/metadata/received_on': '2018-11-06T18:30:00.000000Z',
        })


class ExportOnlyTests(SimpleTestCase):

    def test_create_patient(self):
        """
        ValueSource instances with direction set to DIRECTION_IMPORT
        should not be exported.
        """
        requests = mock.Mock()
        requests.post.return_value.status_code = 500
        info = mock.Mock(
            updates={'sex': 'M', 'dob': '1918-07-18'},
            extra_fields={},
        )
        case_config = copy.deepcopy(CASE_CONFIG)
        case_config['patient_identifiers'] = {}
        case_config['person_preferred_name'] = {}
        case_config['person_preferred_address'] = {}
        case_config['person_attributes'] = {}

        case_config['person_properties']['gender']['direction'] = DIRECTION_IMPORT
        case_config['person_properties']['birthdate']['direction'] = DIRECTION_EXPORT
        case_config = OpenmrsCaseConfig(case_config)

        create_patient(requests, info, case_config)
        requests.post.assert_called_with(
            '/ws/rest/v1/patient/',
            json={'person': {'birthdate': '1918-07-18'}}
        )


class AllowedToForwardTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(AllowedToForwardTests, cls).setUpClass()
        cls.owner = CommCareUser.create(DOMAIN, 'chw@example.com', '123')

    @classmethod
    def tearDownClass(cls):
        cls.owner.delete()
        super(AllowedToForwardTests, cls).tearDownClass()

    def test_update_from_openmrs(self):
        """
        payloads from OpenMRS should not be forwarded back to OpenMRS
        """
        payload = XFormInstanceSQL(
            domain=DOMAIN,
            xmlns=XMLNS_OPENMRS,
        )
        repeater = OpenmrsRepeater()
        self.assertFalse(repeater.allowed_to_forward(payload))

    def test_excluded_case_type(self):
        """
        If the repeater has white-listed case types, excluded case types should not be forwarded
        """
        case_id = uuid.uuid4().hex
        form_payload, cases = _create_case(
            domain=DOMAIN, case_id=case_id, case_type='notpatient', owner_id=self.owner.get_id
        )
        repeater = OpenmrsRepeater()
        repeater.white_listed_case_types = ['patient']
        self.assertFalse(repeater.allowed_to_forward(form_payload))

    def test_allowed_to_forward(self):
        """
        If all criteria pass, the payload should be allowed to forward
        :return:
        """
        case_id = uuid.uuid4().hex
        form_payload, cases = _create_case(domain=DOMAIN, case_id=case_id, owner_id=self.owner.get_id)
        repeater = OpenmrsRepeater()
        self.assertTrue(repeater.allowed_to_forward(form_payload))


class CaseLocationTests(LocationHierarchyTestCase):

    domain = DOMAIN
    location_type_names = ['province', 'city', 'suburb']
    location_structure = [
        ('Western Cape', [
            ('Cape Town', [
                ('Gardens', []),
            ]),
        ]),
        ('Gauteng', [
            ('Johannesburg', [])
        ])
    ]

    @classmethod
    def setUpClass(cls):
        cls.openmrs_capetown_uuid = '50017a7f-296d-4ab9-8d3a-b9498bcbf385'
        with mock.patch('corehq.apps.locations.document_store.publish_location_saved', mock.Mock()):
            super(CaseLocationTests, cls).setUpClass()

            cape_town = cls.locations['Cape Town']
            cape_town.metadata[LOCATION_OPENMRS_UUID] = cls.openmrs_capetown_uuid
            cape_town.save()

    def tearDown(self):
        delete_all_users()
        for repeater in OpenmrsRepeater.by_domain(self.domain):
            repeater.delete()

    @classmethod
    def tearDownClass(cls):
        with mock.patch('corehq.apps.locations.document_store.publish_location_saved', mock.Mock()):
            super(CaseLocationTests, cls).tearDownClass()

    def test_owner_is_location(self):
        """
        get_case_location should return case owner when owner is a location
        """
        joburg = self.locations['Johannesburg']
        form, (case, ) = _create_case(domain=self.domain, case_id=uuid.uuid4().hex, owner_id=joburg.location_id)
        location = get_case_location(case)
        self.assertEqual(location, joburg)

    def test_owner_has_primary_location(self):
        """
        get_case_location should return case owner's location when owner is a mobile worker
        """
        gardens = self.locations['Gardens']
        self.owner = CommCareUser.create(self.domain, 'gardens_user', '***', location=gardens)
        form, (case, ) = _create_case(domain=self.domain, case_id=uuid.uuid4().hex, owner_id=self.owner.get_id)
        location = get_case_location(case)
        self.assertEqual(location, gardens)

    def test_owner_has_no_locations(self):
        """
        get_case_location should return None when owner has no location
        """
        self.owner = CommCareUser.create(self.domain, 'no_location', '***')
        form, (case, ) = _create_case(domain=self.domain, case_id=uuid.uuid4().hex, owner_id=self.owner.get_id)
        location = get_case_location(case)
        self.assertIsNone(location)

    def test_no_owner(self):
        """
        get_case_location should return None when the case has no owner
        """
        form, (case, ) = _create_case(domain=self.domain, case_id=uuid.uuid4().hex, owner_id=None)
        location = get_case_location(case)
        self.assertIsNone(location)

    def test_openmrs_location_uuid_set(self):
        """
        get_ancestor_location_openmrs_uuid should return the OpenMRS
        location UUID that corresponds to a case's location
        """
        cape_town = self.locations['Cape Town']
        case_id = uuid.uuid4().hex
        form, (case, ) = _create_case(domain=self.domain, case_id=case_id, owner_id=cape_town.location_id)

        self.assertEqual(
            get_ancestor_location_openmrs_uuid(self.domain, case_id),
            self.openmrs_capetown_uuid
        )

    def test_openmrs_location_uuid_ancestor(self):
        """
        get_ancestor_location_openmrs_uuid should return the OpenMRS
        location UUID that corresponds to a case's location's ancestor
        """
        gardens = self.locations['Gardens']
        self.assertIsNone(gardens.metadata.get(LOCATION_OPENMRS_UUID))

        case_id = uuid.uuid4().hex
        form, (case, ) = _create_case(domain=self.domain, case_id=case_id, owner_id=gardens.location_id)

        self.assertEqual(
            get_ancestor_location_openmrs_uuid(self.domain, case_id),
            self.openmrs_capetown_uuid
        )

    def test_openmrs_location_uuid_none(self):
        """
        get_ancestor_location_openmrs_uuid should return None if a
        case's location and its ancestors do not have an OpenMRS
        location UUID
        """
        joburg = self.locations['Johannesburg']
        self.assertIsNone(joburg.metadata.get(LOCATION_OPENMRS_UUID))

        case_id = uuid.uuid4().hex
        form, (case, ) = _create_case(domain=self.domain, case_id=case_id, owner_id=joburg.location_id)

        self.assertIsNone(get_ancestor_location_openmrs_uuid(self.domain, case_id))

    def test_get_case_location_ancestor_repeaters_same(self):
        """
        get_case_location_ancestor_repeaters should return the repeater at the same location as the case
        """
        gardens = self.locations['Gardens']
        form, (case, ) = _create_case(domain=self.domain, case_id=uuid.uuid4().hex, owner_id=gardens.location_id)
        gardens_repeater = OpenmrsRepeater.wrap({
            'doc_type': 'OpenmrsRepeater',
            'domain': self.domain,
            'location_id': gardens.location_id,
        })
        gardens_repeater.save()

        repeaters = get_case_location_ancestor_repeaters(case)
        self.assertEqual(repeaters, [gardens_repeater])

    def test_get_case_location_ancestor_repeaters_multi(self):
        """
        get_case_location_ancestor_repeaters should return the repeater at the closest ancestor location
        """
        form, (gardens_case, ) = _create_case(
            domain=self.domain,
            case_id=uuid.uuid4().hex,
            owner_id=self.locations['Gardens'].location_id
        )
        cape_town_repeater = OpenmrsRepeater.wrap({
            'doc_type': 'OpenmrsRepeater',
            'domain': self.domain,
            'location_id': self.locations['Cape Town'].location_id,
        })
        cape_town_repeater.save()
        western_cape_repeater = OpenmrsRepeater.wrap({
            'doc_type': 'OpenmrsRepeater',
            'domain': self.domain,
            'location_id': self.locations['Western Cape'].location_id,
        })
        western_cape_repeater.save()

        repeaters = get_case_location_ancestor_repeaters(gardens_case)
        self.assertEqual(repeaters, [cape_town_repeater])

    def test_get_case_location_ancestor_repeaters_none(self):
        """
        get_case_location_ancestor_repeaters should not return repeaters if there are none at ancestor locations
        """
        gardens = self.locations['Gardens']
        form, (case, ) = _create_case(domain=self.domain, case_id=uuid.uuid4().hex, owner_id=gardens.location_id)

        repeaters = get_case_location_ancestor_repeaters(case)
        self.assertEqual(repeaters, [])


class GetPatientTest(SimpleTestCase):

    def test_get_patient_by_identifier(self):
        response_mock = mock.Mock()
        response_mock.json.return_value = PATIENT_SEARCH_RESPONSE
        requests_mock = mock.Mock()
        requests_mock.get.return_value = response_mock

        patient = get_patient_by_identifier(
            requests_mock, 'e2b966d0-1d5f-11e0-b929-000c29ad1d07', '11111111/11/1111')
        self.assertEqual(patient['uuid'], '5ba94fa2-9cb3-4ae6-b400-7bf45783dcbf')


class FindPatientTest(SimpleTestCase):

    def test_create_missing(self):
        """
        create_patient should be called if PatientFinder.create_missing is set
        """
        openmrs_config = OpenmrsConfig.wrap({
            'case_config': {
                'patient_finder': {
                    'create_missing': {
                        'doc_type': 'ConstantString',
                        'value': 'True',
                        'external_data_type': OPENMRS_DATA_TYPE_BOOLEAN,
                    },
                    'doc_type': 'WeightedPropertyPatientFinder',
                    'searchable_properties': [],
                    'property_weights': [],
                },
                'patient_identifiers': {},
                'match_on_ids': [],
                'person_properties': {},
                'person_preferred_address': {},
                'person_preferred_name': {},
            },
            'form_configs': [],
        })

        with mock.patch('corehq.motech.openmrs.repeater_helpers.CaseAccessors') as CaseAccessorsPatch, \
                mock.patch('corehq.motech.openmrs.repeater_helpers.create_patient') as create_patient_patch:
            requests = mock.Mock()
            info = mock.Mock(case_id='123')
            CaseAccessorsPatch.return_value = mock.Mock(get_case=mock.Mock())
            create_patient_patch.return_value = None

            find_or_create_patient(requests, DOMAIN, info, openmrs_config)

            create_patient_patch.assert_called()


class SaveMatchIdsTests(SimpleTestCase):

    def setUp(self):
        self.case = mock.Mock()
        self.case.domain = DOMAIN
        self.case.get_id = 'deadbeef'
        self.case_config = copy.deepcopy(CASE_CONFIG)
        self.patient = PATIENT_SEARCH_RESPONSE['results'][0]

    @mock.patch('corehq.motech.openmrs.repeater_helpers.submit_case_blocks')
    @mock.patch('corehq.motech.openmrs.repeater_helpers.CaseBlock')
    def test_save_openmrs_uuid(self, case_block_mock, _):
        self.case_config['patient_identifiers']['uuid']['case_property'] = 'openmrs_uuid'
        save_match_ids(self.case, self.case_config, self.patient)
        case_block_mock.assert_called_with(
            case_id='deadbeef',
            create=False,
            update={'openmrs_uuid': '672c4a51-abad-4b5e-950c-10bc262c9c1a'}
        )

    @mock.patch('corehq.motech.openmrs.repeater_helpers.submit_case_blocks')
    @mock.patch('corehq.motech.openmrs.repeater_helpers.CaseBlock')
    def test_save_external_id(self, case_block_mock, _):
        self.case_config['patient_identifiers']['uuid']['case_property'] = 'external_id'
        save_match_ids(self.case, self.case_config, self.patient)
        case_block_mock.assert_called_with(
            case_id='deadbeef',
            create=False,
            external_id='672c4a51-abad-4b5e-950c-10bc262c9c1a',
            update={}
        )


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.openmrs.repeater_helpers)
        self.assertEqual(results.failed, 0)
