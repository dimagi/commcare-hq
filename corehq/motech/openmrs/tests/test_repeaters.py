from __future__ import absolute_import
from __future__ import unicode_literals
import doctest
import os
import uuid
from unittest import TestCase
import mock
from casexml.apps.case.models import CommCareCase
from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.openmrs.const import LOCATION_OPENMRS_UUID
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.util.test_utils import TestFileMixin, _create_case
import corehq.motech.openmrs.repeater_helpers
from corehq.motech.openmrs.repeater_helpers import (
    CaseTriggerInfo,
    get_case_location,
    get_case_location_ancestor_repeaters,
    get_form_question_values,
    get_openmrs_location_uuid,
    get_patient_by_uuid,
    get_relevant_case_updates_from_form_json,
)


DOMAIN = 'openmrs-repeater-tests'


@mock.patch.object(CaseAccessors, 'get_cases', lambda self, case_ids, ordered=False: [{
    '65e55473-e83b-4d78-9dde-eaf949758997': CommCareCase(
        type='paciente', case_id='65e55473-e83b-4d78-9dde-eaf949758997')
}[case_id] for case_id in case_ids])
class OpenmrsRepeaterTest(TestCase, TestFileMixin):
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


class GetPatientByUuidTests(TestCase):

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


class GetFormQuestionValuesTests(TestCase):

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
        with mock.patch('corehq.apps.locations.document_store.publish_location_saved', mock.Mock()):
            super(CaseLocationTests, cls).setUpClass()

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

    def test_openmrs_location_uuid_set(self):
        """
        get_openmrs_location_uuid should return the OpenMRS location UUID that corresponds to a case's location
        """
        openmrs_capetown_uuid = '50017a7f-296d-4ab9-8d3a-b9498bcbf385'
        cape_town = self.locations['Cape Town']
        cape_town.metadata[LOCATION_OPENMRS_UUID] = openmrs_capetown_uuid
        with mock.patch('corehq.apps.locations.document_store.publish_location_saved', mock.Mock()):
            cape_town.save()

        case_id = uuid.uuid4().hex
        form, (case, ) = _create_case(domain=self.domain, case_id=case_id, owner_id=cape_town.location_id)

        self.assertEqual(
            get_openmrs_location_uuid(self.domain, case_id),
            openmrs_capetown_uuid
        )

    def test_openmrs_location_uuid_none(self):
        """
        get_openmrs_location_uuid should return the OpenMRS location UUID that corresponds to a case's location
        """
        gardens = self.locations['Gardens']
        self.assertIsNone(gardens.metadata.get(LOCATION_OPENMRS_UUID))

        case_id = uuid.uuid4().hex
        form, (case, ) = _create_case(domain=self.domain, case_id=case_id, owner_id=gardens.location_id)

        self.assertIsNone(get_openmrs_location_uuid(self.domain, case_id))

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


class DocTests(TestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.openmrs.repeater_helpers)
        self.assertEqual(results.failed, 0)
