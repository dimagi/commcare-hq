from __future__ import absolute_import
from __future__ import unicode_literals
import doctest
import os
from collections import namedtuple
from unittest import TestCase
import mock
from casexml.apps.case.models import CommCareCase
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.util.test_utils import TestFileMixin
import corehq.motech.openmrs.repeater_helpers
from corehq.motech.openmrs.repeater_helpers import (
    get_patient_by_uuid,
    get_relevant_case_updates_from_form_json,
    CaseTriggerInfo,
    get_form_question_values,
    get_case_location,
    get_case_location_ancestor_repeaters,
)


DOMAIN = 'test-domain'


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


class CaseLocationTests(TestCase):

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
    FakeLocation('56_barnet_st'),
    FakeLocation('gardens'),
    FakeLocation('cape_town'),
    FakeLocation('western_cape'),
    FakeLocation('south_africa'),
]
joburg_ancestors = [
    FakeLocation('johannesburg'),
    FakeLocation('gauteng'),
    FakeLocation('south_africa'),
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


class AncestorRepeaterTests(TestCase):

    @mock.patch('corehq.motech.openmrs.repeater_helpers.get_case_location',
                mock.Mock(return_value=joburg))
    @mock.patch('corehq.apps.locations.models.SQLLocation.get_ancestors',
                mock.Mock(return_value=joburg_ancestors))
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
    @mock.patch('corehq.apps.locations.models.SQLLocation.get_ancestors',
                mock.Mock(return_value=cape_town_ancestors))
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


class DocTests(TestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.openmrs.repeater_helpers)
        self.assertEqual(results.failed, 0)
