import json
from datetime import datetime
from django.test import TestCase

from casexml.apps.case.mock.mock import CaseIndex
from casexml.apps.case.const import CASE_INDEX_EXTENSION
from corehq.util.test_utils import flag_enabled
from custom.enikshay.const import PRIMARY_PHONE_NUMBER, BACKUP_PHONE_NUMBER
from custom.enikshay.integrations.nikshay.repeaters import NikshayRegisterPatientRepeater
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin

from custom.enikshay.integrations.nikshay.repeater_generator import NikshayRegisterPatientPayloadGenerator, \
    ENIKSHAY_ID
from corehq.form_processor.tests.utils import run_with_all_backends
from casexml.apps.case.mock import CaseStructure
from corehq.apps.repeaters.models import RepeatRecord
from corehq.apps.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from casexml.apps.case.tests.util import delete_all_cases


class MockResponse(object):
    def __init__(self, status_code, json_data):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


class NikshayRepeaterTestBase(ENikshayCaseStructureMixin, TestCase):
    def setUp(self):
        super(NikshayRepeaterTestBase, self).setUp()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def tearDown(self):
        super(NikshayRepeaterTestBase, self).tearDown()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.utcnow())

    def _create_nikshay_enabled_case(self):
        nikshay_enabled_case_on_update = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'case_type': 'episode',
                "update": dict(
                    episode_pending_registration='no',
                )
            }
        )

        return self.create_case(nikshay_enabled_case_on_update)

    def _create_nikshay_registered_case(self):
        nikshay_registered_case = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'create': True,
                'case_type': 'episode',
                "update": dict(
                    nikshay_registered='true',
                )
            }
        )
        self.create_case(nikshay_registered_case)

    def test_not_available_for_domain(self):
        self.assertFalse(NikshayRegisterPatientRepeater.available_for_domain(self.domain))

    @flag_enabled('NIKSHAY_INTEGRATION')
    def test_available_for_domain(self):
        self.assertTrue(NikshayRegisterPatientRepeater.available_for_domain(self.domain))

    @property
    def episode(self):
        return CaseStructure(
            case_id=self.episode_id,
            attrs={
                'create': True,
                'case_type': 'episode',
                "update": dict(
                    person_name="Pippin",
                    opened_on=datetime(1989, 6, 11, 0, 0),
                    patient_type_choice="treatment_after_lfu",
                    hiv_status="reactive",
                    episode_type="confirmed_tb",
                    default_adherence_confidence="high",
                    occupation='engineer',
                    date_of_diagnosis='2014-09-09',
                    treatment_initiation_date='2015-03-03',
                    disease_classification='extra_pulmonary',
                    treatment_supporter_first_name='awesome',
                    treatment_supporter_last_name='dot',
                    treatment_supporter_mobile_number='123456789',
                    treatment_supporter_designation='ngo_volunteer',
                    site_choice='pleural_effusion'
                )
            },
            indices=[CaseIndex(
                self.occurrence,
                identifier='host',
                relationship=CASE_INDEX_EXTENSION,
                related_type=self.occurrence.attrs['case_type'],
            )],
        )

    @property
    def person(self):
        return CaseStructure(
            case_id=self.person_id,
            attrs={
                "case_type": "person",
                "create": True,
                "update": {
                    'name': "Pippin",
                    'aadhaar_number': "499118665246",
                    PRIMARY_PHONE_NUMBER: self.primary_phone_number,
                    BACKUP_PHONE_NUMBER: self.secondary_phone_number,
                    'merm_id': "123456789",
                    'dob': "1987-08-15",
                    'age': 20,
                    'sex': 'male',
                    'current_address': 'Mr. Everest',
                    'secondary_contact_name_address': 'Mrs. Everestie',
                    'previous_tb_treatment': 'yes'
                }
            },
        )


class TestNikshayRegisterPatientRepeater(NikshayRepeaterTestBase):

    def setUp(self):
        super(TestNikshayRegisterPatientRepeater, self).setUp()

        self.repeater = NikshayRegisterPatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
            username='test-user'
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    @run_with_all_backends
    def test_trigger(self):
        # nikshay not enabled
        self.create_case(self.episode)
        self.assertEqual(0, len(self.repeat_records().all()))

        # nikshay enabled, should register a repeat record
        self._create_nikshay_enabled_case()
        self.assertEqual(1, len(self.repeat_records().all()))
        #
        # set as registered, should not register a new repeat record
        self._create_nikshay_registered_case()
        self.assertEqual(1, len(self.repeat_records().all()))

    @run_with_all_backends
    def test_payload_general_properties(self):
        self.create_case(self.episode)
        episode_case = self._create_nikshay_enabled_case()
        self.assertEqual(1, len(self.repeat_records().all()))
        repeat_record = self.repeat_records().all()[0]
        payload = (json.loads(
            NikshayRegisterPatientPayloadGenerator(self.repeater)
            .get_payload(repeat_record, episode_case[0]))
        )
        self.assertEqual(payload['Source'], ENIKSHAY_ID)
        self.assertEqual(payload['Local_ID'], self.person_id)
        self.assertEqual(payload['regBy'], self.repeater.username)

    @run_with_all_backends
    def test_payload_person_properties(self):
        self.create_case(self.episode)
        episode_case = self._create_nikshay_enabled_case()
        self.assertEqual(1, len(self.repeat_records().all()))
        repeat_record = self.repeat_records().all()[0]
        payload = (json.loads(
            NikshayRegisterPatientPayloadGenerator(self.repeater).get_payload(repeat_record, episode_case[0]))
        )
        self.assertEqual(payload['pname'], 'Pippin')
        self.assertEqual(payload['page'], '20')
        self.assertEqual(payload['pgender'], 'M')
        self.assertEqual(payload['paddress'], 'Mr. Everest')
        self.assertEqual(payload['pmob'], self.primary_phone_number)
        self.assertEqual(payload['cname'], 'Mrs. Everestie')
        self.assertEqual(payload['caddress'], 'Mrs. Everestie')
        self.assertEqual(payload['cmob'], self.secondary_phone_number)
        self.assertEqual(payload['pcategory'], '2')

    @run_with_all_backends
    def test_payload_episode_properties(self):
        self.create_case(self.episode)
        episode_case = self._create_nikshay_enabled_case()
        self.assertEqual(1, len(self.repeat_records().all()))
        repeat_record = self.repeat_records().all()[0]
        payload = (json.loads(
            NikshayRegisterPatientPayloadGenerator(self.repeater).get_payload(repeat_record, episode_case[0]))
        )
        self.assertEqual(payload['sitedetail'], 2)
        self.assertEqual(payload['Ptype'], '6')
        self.assertEqual(payload['poccupation'], 4)
        self.assertEqual(payload['dotname'], 'awesome dot')
        self.assertEqual(payload['dotmob'], '123456789')
        self.assertEqual(payload['disease_classification'], 'EP')
        self.assertEqual(payload['pregdate'], '2014-09-09')
        self.assertEqual(payload['ptbyr'], '2014')
        self.assertEqual(payload['dotpType'], '5')
        self.assertEqual(payload['dotdesignation'], 'ngo_volunteer')
        self.assertEqual(payload['dateofInitiation'], '2015-03-03')
