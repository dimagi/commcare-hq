from __future__ import absolute_import
from __future__ import unicode_literals
import doctest
import json
import os
import uuid
from collections import namedtuple
import unittest
import mock
from django.test import TestCase as DjangoTestCase

from casexml.apps.case.models import CommCareCase
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import XFormInstanceSQL
# from corehq.form_processor.tests.test_case_dbaccessor import _create_case
from corehq.motech.openmrs.const import XMLNS_OPENMRS
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.util.test_utils import TestFileMixin, _create_case
import corehq.motech.openmrs.repeater_helpers
from corehq.motech.openmrs.repeater_helpers import (
    get_patient_by_uuid,
    get_relevant_case_updates_from_form_json,
    CaseTriggerInfo,
    get_form_question_values,
    get_case_location,
    get_case_location_ancestor_repeaters,
    get_patient_by_identifier,
)


DOMAIN = 'test-domain'
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


@mock.patch.object(CaseAccessors, 'get_cases', lambda self, case_ids, ordered=False: [{
    '65e55473-e83b-4d78-9dde-eaf949758997': CommCareCase(
        type='paciente', case_id='65e55473-e83b-4d78-9dde-eaf949758997')
}[case_id] for case_id in case_ids])
class OpenmrsRepeaterTest(unittest.TestCase, TestFileMixin):
    file_path = ('data',)
    root = os.path.dirname(__file__)

    def test_get_case_updates_for_registration(self):
        self.assertEqual(
            get_relevant_case_updates_from_form_json(
                'openmrs-repeater-test', self.get_json('registration'), ['paciente'], {}),
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
        self.assertEqual(
            get_relevant_case_updates_from_form_json(
                'openmrs-repeater-test', self.get_json('followup'), ['paciente'], {}),
            [
                CaseTriggerInfo(
                    case_id='65e55473-e83b-4d78-9dde-eaf949758997',
                    updates={
                        'estado_tarv': '1',
                        'tb': '1',
                    },
                    created=False,
                    closed=False,
                    extra_fields={},
                    form_question_values={},
                )
            ]
        )


class GetPatientByUuidTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.patient = {
            'uuid': 'c83d9989-585f-4db3-bf55-ca1d0ee7c0af',
            'display': 'Luis Safiana Bassilo'
        }
        response = mock.Mock()
        response.json.return_value = cls.patient
        cls.requests = mock.Mock()
        cls.requests.get.return_value = response

    @classmethod
    def tearDownClass(cls):
        pass

    def test_none(self):
        patient = get_patient_by_uuid(self.requests, uuid=None)
        self.assertIsNone(patient)

    def test_empty(self):
        patient = get_patient_by_uuid(self.requests, uuid='')
        self.assertIsNone(patient)

    def test_invalid_uuid(self):
        patient = get_patient_by_uuid(self.requests, uuid='c83d9989585f4db3bf55ca1d0ee7c0af')
        # OpenMRS UUIDs have "-" separators
        self.assertIsNone(patient)

    def test_valid_uuid(self):
        patient = get_patient_by_uuid(self.requests, uuid='c83d9989-585f-4db3-bf55-ca1d0ee7c0af')
        self.assertEqual(patient, self.patient)


class GetFormQuestionValuesTests(unittest.TestCase):

    def test_unicode_answer(self):
        value = get_form_question_values({'form': {'foo': {'bar': u'b\u0105z'}}})
        self.assertEqual(value, {'/data/foo/bar': u'b\u0105z'})

    def test_utf8_answer(self):
        value = get_form_question_values({'form': {'foo': {'bar': b'b\xc4\x85z'}}})
        self.assertEqual(value, {'/data/foo/bar': b'b\xc4\x85z'})

    def test_unicode_question(self):
        # Form Builder questions are expected to be ASCII
        value = get_form_question_values({'form': {'foo': {u'b\u0105r': 'baz'}}})
        self.assertEqual(value, {u'/data/foo/b\u0105r': 'baz'})

    def test_utf8_question(self):
        # Form Builder questions are expected to be ASCII
        value = get_form_question_values({'form': {'foo': {b'b\xc4\x85r': 'baz'}}})
        self.assertEqual(value, {u'/data/foo/b\u0105r': 'baz'})


class AllowedToForwardTests(DjangoTestCase):

    @classmethod
    def setUpClass(cls):
        cls.owner = CommCareUser.create(DOMAIN, 'chw@example.com', '123')

    @classmethod
    def tearDownClass(cls):
        cls.owner.delete()

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


joburg = SQLLocation(location_id='johannesburg')
cape_town = SQLLocation(location_id='cape_town')
FakeLocation = namedtuple('FakeLocation', 'location_id')


does_not_exist_mock = mock.Mock(side_effect=SQLLocation.DoesNotExist)
cape_town_chw_doc = {
    'doc_type': 'CommCareUser',
    '_id': 'cape_town_chw',
    'domain': DOMAIN,
    'username': 'chw@cape_town.org',
    'user_data': {},
    'location_id': 'cape_town',
}
cape_town_chw_owner = mock.Mock(return_value=mock.Mock(get=lambda owner_id: cape_town_chw_doc))

nowhere_chw_doc = {
    'doc_type': 'CommCareUser',
    '_id': 'nowhere_chw',
    'domain': DOMAIN,
    'username': 'chw@nowhere.org',
    'user_data': {},
    'location_id': None,
}
nowhere_chw_owner = mock.Mock(return_value=mock.Mock(get=lambda owner_id: nowhere_chw_doc))

everywhere_chw_doc = {
    'doc_type': 'CommCareUser',
    '_id': 'everywhere_chw',
    'domain': DOMAIN,
    'username': 'chw@everywhere.org',
    'user_data': {},
    'location_id': None,
    'assigned_location_ids': ['cape_town', 'johannesburg']
}
everywhere_chw_owner = mock.Mock(return_value=mock.Mock(get=lambda owner_id: everywhere_chw_doc))


class CaseLocationTests(unittest.TestCase):

    @mock.patch('corehq.apps.locations.models.SQLLocation.objects.get', mock.Mock(return_value=joburg))
    def test_owner_is_location(self):
        """
        get_case_location should return case owner when owner is a location
        """
        joburg_patient = CommCareCase(domain=DOMAIN, owner_id='johannesburg')
        location = get_case_location(joburg_patient)
        self.assertIsInstance(location, SQLLocation)
        self.assertEqual(location.location_id, 'johannesburg')

    @mock.patch('corehq.apps.locations.models.SQLLocation.objects.get', does_not_exist_mock)
    @mock.patch('corehq.apps.users.models.CouchUser.get_db', cape_town_chw_owner)
    @mock.patch('corehq.apps.users.models.DomainMembership.location_id', cape_town_chw_doc['location_id'])
    @mock.patch('corehq.apps.locations.models.SQLLocation.by_location_id',
                mock.Mock(side_effect=lambda loc_id: FakeLocation(loc_id) if loc_id else None))
    def test_owner_has_primary_location(self):
        """
        get_case_location should return case owner's location when owner is a mobile worker
        """
        cape_town_patient = CommCareCase(domain=DOMAIN, owner_id='cape_town_chw')
        location = get_case_location(cape_town_patient)
        self.assertIsInstance(location, FakeLocation)
        self.assertEqual(location.location_id, 'cape_town')

    @mock.patch('corehq.apps.locations.models.SQLLocation.objects.get', does_not_exist_mock)
    @mock.patch('corehq.apps.users.models.CouchUser.get_db', nowhere_chw_owner)
    @mock.patch('corehq.apps.users.models.DomainMembership.location_id', nowhere_chw_doc['location_id'])
    @mock.patch('corehq.apps.locations.models.SQLLocation.by_location_id',
                mock.Mock(side_effect=lambda loc_id: FakeLocation(loc_id) if loc_id else None))
    def test_owner_has_no_locations(self):
        """
        get_case_location should return None when owner has no location
        """
        nowhere_patient = CommCareCase(domain=DOMAIN, owner_id='nowhere_chw')
        location = get_case_location(nowhere_patient)
        self.assertIsNone(location)

    @mock.patch('corehq.apps.locations.models.SQLLocation.objects.get', does_not_exist_mock)
    @mock.patch('corehq.apps.users.models.CouchUser.get_db', everywhere_chw_owner)
    @mock.patch('corehq.apps.users.models.DomainMembership.location_id', everywhere_chw_doc['location_id'])
    @mock.patch('corehq.apps.locations.models.SQLLocation.by_location_id',
                mock.Mock(side_effect=lambda loc_id: FakeLocation(loc_id) if loc_id else None))
    def test_owner_has_assigned_locations(self):
        """
        get_case_location should return None when owner has no primary location
        """
        everywhere_patient = CommCareCase(domain=DOMAIN, owner_id='everywhere_chw')
        location = get_case_location(everywhere_patient)
        self.assertIsNone(location)


cape_town_ancestors = [
    'south_africa',
    'western_cape',
    'cape_town',
    'gardens',
    '56_barnet_st',
]
joburg_ancestors = [
    'south_africa',
    'gauteng',
    'johannesburg',
]
cape_town_repeater = OpenmrsRepeater(
    _id='0000',
    location_id='cape_town'
)
western_cape_repeater = OpenmrsRepeater(
    _id='1111',
    location_id='western_cape'
)
joburg_repeater = OpenmrsRepeater(
    _id='2222',
    location_id='johannesburg'
)
get_repeaters_mock = mock.Mock(return_value=[cape_town_repeater, western_cape_repeater, joburg_repeater])


class AncestorRepeaterTests(unittest.TestCase):

    @mock.patch('corehq.motech.openmrs.repeater_helpers.get_case_location',
                mock.Mock(return_value=joburg))
    @mock.patch('corehq.apps.locations.models.SQLLocation.path', joburg_ancestors)
    @mock.patch('corehq.apps.locations.models.SQLLocation.by_location_id',
                mock.Mock(side_effect=lambda loc_id: FakeLocation(loc_id) if loc_id else None))
    @mock.patch('corehq.motech.openmrs.dbaccessors.get_openmrs_repeaters_by_domain', get_repeaters_mock)
    def test_get_case_location_ancestor_repeaters_self(self):
        """
        The repeater should be returned when it is at the same location as the case
        """
        joburg_patient = CommCareCase()  # because get_case_location mock returns joburg
        repeaters = get_case_location_ancestor_repeaters(joburg_patient)
        self.assertEqual(repeaters, [joburg_repeater])

    @mock.patch('corehq.motech.openmrs.repeater_helpers.get_case_location',
                mock.Mock(return_value=cape_town))
    @mock.patch('corehq.apps.locations.models.SQLLocation.path', cape_town_ancestors)
    @mock.patch('corehq.apps.locations.models.SQLLocation.by_location_id',
                mock.Mock(side_effect=lambda loc_id: FakeLocation(loc_id) if loc_id else None))
    @mock.patch('corehq.motech.openmrs.dbaccessors.get_openmrs_repeaters_by_domain', get_repeaters_mock)
    def test_get_case_location_ancestor_repeaters_multi(self):
        """
        When a case location has multiple ancestors with repeaters, the
        repeater of the closest ancestor should be returned
        """
        cape_town_patient = CommCareCase()  # because get_case_location mock returns cape_town
        repeaters = get_case_location_ancestor_repeaters(cape_town_patient)
        self.assertEqual(repeaters, [cape_town_repeater])


class GetPatientTest(unittest.TestCase):

    def test_get_patient_by_identifier(self):
        response_mock = mock.Mock()
        response_mock.json.return_value = PATIENT_SEARCH_RESPONSE
        requests_mock = mock.Mock()
        requests_mock.get.return_value = response_mock

        patient = get_patient_by_identifier(
            requests_mock, 'e2b966d0-1d5f-11e0-b929-000c29ad1d07', '11111111/11/1111')
        self.assertEqual(patient['uuid'], '5ba94fa2-9cb3-4ae6-b400-7bf45783dcbf')


class DocTests(unittest.TestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.openmrs.repeater_helpers)
        self.assertEqual(results.failed, 0)
