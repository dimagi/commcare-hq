from __future__ import absolute_import
import doctest
import os
from django.test import SimpleTestCase
import mock
from casexml.apps.case.models import CommCareCase
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.test_utils import TestFileMixin
import corehq.motech.openmrs.repeater_helpers
from corehq.motech.openmrs.repeater_helpers import \
    get_relevant_case_updates_from_form_json, CaseTriggerInfo


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
                        u'case_name': u'Elsa',
                        u'case_type': u'paciente',
                        u'estado_tarv': u'1',
                        u'owner_id': u'9393007a6921eecd4a9f20eefb5c7a8e',
                        u'tb': u'0',
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
                        u'estado_tarv': u'1',
                        u'tb': u'1',
                    },
                    created=False,
                    closed=False,
                    extra_fields={},
                    form_question_values={},
                )
            ]
        )


class DocTests(SimpleTestCase):

    def test_doctests(self):
        results = doctest.testmod(corehq.motech.openmrs.repeater_helpers)
        self.assertEqual(results.failed, 0)
