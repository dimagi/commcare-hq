from __future__ import absolute_import
from __future__ import unicode_literals
import doctest
import os
from django.test import SimpleTestCase
import mock
from casexml.apps.case.models import CommCareCase
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.test_utils import TestFileMixin
import corehq.motech.openmrs.repeater_helpers
from corehq.motech.openmrs.repeater_helpers import (
    get_patient_by_uuid,
    get_relevant_case_updates_from_form_json,
    CaseTriggerInfo
)


@mock.patch.object(CaseAccessors, 'get_cases', lambda self, case_ids, ordered=False: [{
    '65e55473-e83b-4d78-9dde-eaf949758997': CommCareCase(
        type='paciente', case_id='65e55473-e83b-4d78-9dde-eaf949758997')
}[case_id] for case_id in case_ids])
class OpenmrsRepeaterTest(SimpleTestCase, TestFileMixin):
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


class GetPatientByUuidTests(SimpleTestCase):

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


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.openmrs.repeater_helpers)
        self.assertEqual(results.failed, 0)
