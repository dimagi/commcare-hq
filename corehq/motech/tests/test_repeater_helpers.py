from django.test.testcases import TestCase
from mock import patch
from corehq.form_processor.models import CommCareCaseSQL
from datetime import datetime
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.repeater_helpers import get_relevant_case_updates_from_form_json


class TestRepeaterHelpers(TestCase):

    def setUp(self):
        self.domain = 'test-domain'
        self.extra_fields = []
        self.form_question_values = {}

        case_1_data = {
            'case_id': '5ca13e74-8ba3-4d0d-l09j-66371e8895dd',
            'domain': self.domain,
            'type': 'paciente',
            'name': 'case1',
            'owner_id': 'owner_1',
            'modified_by': 'modified_by',
        }
        case_2_data = {
            'case_id': '6ca13e74-8ba3-4d0d-l09j-66371e8895dc',
            'domain': self.domain,
            'type': 'casa',
            'name': 'case2',
            'owner_id': 'owner_2',
            'modified_by': 'modified_by',
        }

        self.case_1 = create_commcare_case(case_1_data)
        self.case_2 = create_commcare_case(case_2_data)

    def tearDown(self):
        self.case_1.delete()
        self.case_2.delete()

    @patch.object(CaseAccessors, 'get_cases')
    def test__get_relevant_case_updates_from_form_json_with_case_types(self, get_cases):
        get_cases.return_value = [self.case_1, self.case_2]

        result = get_relevant_case_updates_from_form_json(
            self.domain,
            _get_form_json(),
            ['paciente'],
            self.extra_fields
        )
        self.assertEqual(len(result), 2)

    @patch.object(CaseAccessors, 'get_cases')
    def test__get_relevant_case_updates_from_form_json_without_case_types(self, get_cases):
        get_cases.return_value = [self.case_1, self.case_2]

        result = get_relevant_case_updates_from_form_json(
            self.domain,
            _get_form_json(),
            [],
            self.extra_fields
        )
        self.assertEqual(len(result), 3)


def create_commcare_case(data):
    cccsql = CommCareCaseSQL(
        case_id=data['case_id'],
        domain=data['domain'],
        type=data['type'],
        name=data['name'],
        owner_id=data['owner_id'],
        modified_by=data['modified_by'],
        modified_on=datetime.utcnow(),
        server_modified_on=datetime.utcnow(),
    )
    cccsql.save()
    return cccsql


def _get_form_json():
    return {'app_id': 'APP_ID',
            'archived': False,
            'attachments': {
                'form.xml': {
                    'content_type': 'text/xml',
                    'length': 10975,
                    'url': 'https://www.commcarehq.org/a/infomovel-pepfar'
                           '/api/form/attachment/CONFIDENTIAL/form.xml'
                }
            },
            'build_id': 'BUILD_ID',
            'domain': 'infomovel-pepfar',
            'edited_by_user_id': None,
            'edited_on': None,
            'form': {'#type': 'data',
                     '@name': 'SOME NAME',
                     '@uiVersion': '1',
                     '@version': 'VERSION',
                     '@xmlns': 'http://openrosa.org/formdesigner/IDIDID',
                     'casa_data': {'convivente_cascade': {},
                                   'conviventes_names': {},
                                   'index_cascade': {},
                                   'save_to_case': {'alocar_paciente_casa': {
                                       'case': {'@case_id': '5ca13e74-8ba3-4d0d-l09j-66371e8895dd',
                                                '@date_modified': '2021-06-24T08:43:06.746000Z',
                                                '@user_id': 'USER ID',
                                                '@xmlns': 'http://commcarehq.org/case/transaction/v2',
                                                'index': {
                                                    'parent': {
                                                        '#text': '6ca13e74-8ba3-4d0d-l09j-66371e8895dc',
                                                        '@case_type': '',
                                                        '@relationship': 'child'
                                                    }
                                                }}},
                                       'criar_actualizar_casa': {
                                           'case': {'@case_id': '6ca13e74-8ba3-4d0d-l09j-66371e8895dc',
                                                    '@date_modified': '2021-05-24T08:43:06.746000Z',
                                                    '@user_id': 'USER ID',
                                                    '@xmlns': 'http://commcarehq.org/case/transaction/v2',
                                                    'create': {'case_name': 'CASE NAME',
                                                               'case_type': 'casa',
                                                               'owner_id': 'owner_1'},
                                                    'update': {
                                                        'age_range1': '25-30',
                                                        'age_range2': '25-30 anos',
                                                    }
                                                    }}},
                                   'tb_patient_in_household': '0'},
                     'case': {'@case_id': '5ca13e74-8ba3-4d0d-l09j-66371e8895dd',
                              '@date_modified': '2021-06-24T08:43:06.746000Z',
                              '@user_id': 'USER ID',
                              '@xmlns': 'http://commcarehq.org/case/transaction/v2',
                              'update': {'name': 'John Lennon'}},
                     'confirm_info': {},
                     'confirmar_perfil': {},
                     'imported_properties': {},
                     'indicators_v4': {},
                     'key_workflow_properties': {},
                     'meta': {},
                     'patient_data': {}, },
            'metadata': {},
            }
