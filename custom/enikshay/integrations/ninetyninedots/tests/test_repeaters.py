import json
from datetime import datetime
from django.test import TestCase

from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import conditionally_run_with_all_backends
from casexml.apps.case.mock import CaseStructure
from corehq.apps.repeaters.models import RepeatRecord
from corehq.apps.repeaters.dbaccessors import delete_all_repeat_records, delete_all_repeaters
from casexml.apps.case.tests.util import delete_all_cases

from custom.enikshay.tests.utils import ENikshayCaseStructureMixin, ENikshayLocationStructureMixin
from custom.enikshay.integrations.ninetyninedots.repeater_generators import (
    RegisterPatientPayloadGenerator,
    UpdatePatientPayloadGenerator,
    AdherencePayloadGenerator,
    TreatmentOutcomePayloadGenerator,
)
from custom.enikshay.case_utils import get_person_locations
from custom.enikshay.const import (
    PRIMARY_PHONE_NUMBER,
    MERM_ID,
    PERSON_FIRST_NAME,
    PERSON_LAST_NAME,
    TREATMENT_START_DATE,
    TREATMENT_SUPPORTER_FIRST_NAME,
    TREATMENT_SUPPORTER_LAST_NAME,
    TREATMENT_OUTCOME,
    TREATMENT_OUTCOME_DATE,
)
from custom.enikshay.integrations.ninetyninedots.repeaters import (
    NinetyNineDotsRegisterPatientRepeater,
    NinetyNineDotsUpdatePatientRepeater,
    NinetyNineDotsAdherenceRepeater,
    NinetyNineDotsTreatmentOutcomeRepeater,
)


class MockResponse(object):
    def __init__(self, status_code, json_data):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


class ENikshayRepeaterTestBase(ENikshayCaseStructureMixin, TestCase):
    def setUp(self):
        super(ENikshayRepeaterTestBase, self).setUp()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def tearDown(self):
        super(ENikshayRepeaterTestBase, self).tearDown()

        delete_all_repeat_records()
        delete_all_repeaters()
        delete_all_cases()

    def repeat_records(self):
        return RepeatRecord.all(domain=self.domain, due_before=datetime.utcnow())

    def _create_99dots_enabled_case(self):
        dots_enabled_case = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'case_type': 'episode',
                "update": dict(
                    dots_99_enabled='true',
                )
            }
        )
        self.create_case(dots_enabled_case)

    def _create_99dots_registered_case(self):
        dots_registered_case = CaseStructure(
            case_id=self.episode_id,
            attrs={
                'create': True,
                'case_type': 'episode',
                "update": dict(
                    dots_99_registered='true',
                )
            }
        )
        self.create_case(dots_registered_case)

    def _update_case(self, case_id, case_properties):
        return self.create_case(
            CaseStructure(
                case_id=case_id,
                attrs={
                    "update": case_properties,
                }
            )
        )


class TestRegisterPatientRepeater(ENikshayRepeaterTestBase):

    def setUp(self):
        super(TestRegisterPatientRepeater, self).setUp()

        self.repeater = NinetyNineDotsRegisterPatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    @conditionally_run_with_all_backends
    def test_trigger(self):
        # 99dots not enabled
        self.create_case(self.episode)
        self.assertEqual(0, len(self.repeat_records().all()))

        # enable 99dots, should register a repeat record
        self._create_99dots_enabled_case()
        self.assertEqual(1, len(self.repeat_records().all()))

        # set as registered, shouldn't register a new repeat record
        self._create_99dots_registered_case()
        self.assertEqual(1, len(self.repeat_records().all()))


class TestUpdatePatientRepeater(ENikshayRepeaterTestBase):

    def setUp(self):
        super(TestUpdatePatientRepeater, self).setUp()
        self.repeater = NinetyNineDotsUpdatePatientRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['person']
        self.repeater.save()

    @conditionally_run_with_all_backends
    def test_trigger(self):
        self.create_case_structure()
        self._update_case(self.person_id, {PRIMARY_PHONE_NUMBER: '999999999', })
        self.assertEqual(0, len(self.repeat_records().all()))

        self._create_99dots_registered_case()
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_case(self.person_id, {'name': 'Elrond', })
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_case(self.person_id, {PRIMARY_PHONE_NUMBER: '999999999', })
        self.assertEqual(1, len(self.repeat_records().all()))

    @conditionally_run_with_all_backends
    def test_trigger_multiple_cases(self):
        """Submitting a form with noop case blocks was throwing an exception
        """
        self.create_case_structure()
        self._create_99dots_registered_case()

        empty_case = CaseStructure(
            case_id=self.episode_id,
        )
        person_case = CaseStructure(
            case_id=self.person_id,
            attrs={
                'case_type': 'person',
                'update': {PRIMARY_PHONE_NUMBER: '9999999999'}
            }
        )

        self.factory.create_or_update_cases([empty_case, person_case])
        self.assertEqual(1, len(self.repeat_records().all()))

    @conditionally_run_with_all_backends
    def test_create_person_no_episode(self):
        """On registration this was failing hard if a phone number was added but no episode was created
        http://manage.dimagi.com/default.asp?241290#1245284
        """
        self.create_case(self.person)
        self.assertEqual(0, len(self.repeat_records().all()))


class TestAdherenceRepeater(ENikshayRepeaterTestBase):

    def setUp(self):
        super(TestAdherenceRepeater, self).setUp()
        self.repeater = NinetyNineDotsAdherenceRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['adherence']
        self.repeater.save()

    @conditionally_run_with_all_backends
    def test_trigger(self):
        self.create_case_structure()
        self._create_99dots_registered_case()
        self._create_99dots_enabled_case()
        self.assertEqual(0, len(self.repeat_records().all()))

        self.create_adherence_cases([datetime(2017, 2, 17)])
        self.assertEqual(0, len(self.repeat_records().all()))

        self.create_adherence_cases([datetime(2017, 2, 18)], adherence_source='enikshay')
        self.assertEqual(1, len(self.repeat_records().all()))

        self.create_adherence_cases([datetime(2017, 2, 20)], adherence_source='enikshay')
        self.assertEqual(2, len(self.repeat_records().all()))


class TestTreatmentOutcomeRepeater(ENikshayRepeaterTestBase):

    def setUp(self):
        super(TestTreatmentOutcomeRepeater, self).setUp()
        self.repeater = NinetyNineDotsTreatmentOutcomeRepeater(
            domain=self.domain,
            url='case-repeater-url',
        )
        self.repeater.white_listed_case_types = ['episode']
        self.repeater.save()

    @conditionally_run_with_all_backends
    def test_trigger(self):
        self.create_case_structure()
        self._create_99dots_registered_case()
        self._create_99dots_enabled_case()
        self.assertEqual(0, len(self.repeat_records().all()))

        self._update_case(self.episode_id, {TREATMENT_OUTCOME: 'the_end_of_days'})
        self.assertEqual(1, len(self.repeat_records().all()))

        self._update_case(self.episode_id, {TREATMENT_SUPPORTER_FIRST_NAME: 'boo'})
        self.assertEqual(1, len(self.repeat_records().all()))


class TestPayloadGeneratorBase(ENikshayCaseStructureMixin, ENikshayLocationStructureMixin, TestCase):

    def tearDown(self):
        super(TestPayloadGeneratorBase, self).tearDown()
        delete_all_cases()

    def _get_actual_payload(self, casedb):
        raise NotImplementedError()

    def _assert_payload_equal(self, casedb, expected_numbers):
        person_case = casedb[self.person_id]
        episode_case = casedb[self.episode_id]
        person_case_properties = person_case.dynamic_case_properties()
        episode_case_properties = episode_case.dynamic_case_properties()
        person_locations = get_person_locations(person_case)
        expected_payload = {
            "beneficiary_id": self.person_id,
            "first_name": person_case_properties.get(PERSON_FIRST_NAME, None),
            "last_name": person_case_properties.get(PERSON_LAST_NAME, None),
            "sto_code": person_locations.sto,
            "dto_code": person_locations.dto,
            "tu_code": person_locations.tu,
            "phi_code": person_locations.phi,
            "phone_numbers": expected_numbers,
            "merm_id": person_case_properties.get(MERM_ID, None),
            "treatment_start_date": episode_case_properties.get(TREATMENT_START_DATE, None),
            "treatment_supporter_name": "{} {}".format(
                episode_case_properties.get(TREATMENT_SUPPORTER_FIRST_NAME, ''),
                episode_case_properties.get(TREATMENT_SUPPORTER_LAST_NAME, ''),
            ),
            "treatment_supporter_phone_number": "+91{}".format(self.treatment_supporter_phone[1:]),
        }
        actual_payload = json.loads(self._get_actual_payload(casedb))
        self.assertDictEqual(expected_payload, actual_payload)


class TestRegisterPatientPayloadGenerator(TestPayloadGeneratorBase):

    def _get_actual_payload(self, casedb):
        return RegisterPatientPayloadGenerator(None).get_payload(None, casedb[self.episode_id])

    @conditionally_run_with_all_backends
    def test_get_payload(self):
        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.phi.location_id)

        expected_numbers = u"+91{}, +91{}".format(
            self.primary_phone_number.replace("0", ""),
            self.secondary_phone_number.replace("0", "")
        )
        self._assert_payload_equal(cases, expected_numbers)

    @conditionally_run_with_all_backends
    def test_get_payload_no_numbers(self):
        self.primary_phone_number = None
        self.secondary_phone_number = None
        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.phi.location_id)
        self._assert_payload_equal(cases, None)

    @conditionally_run_with_all_backends
    def test_get_payload_secondary_number_only(self):
        self.primary_phone_number = None
        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.phi.location_id)
        self._assert_payload_equal(cases, u"+91{}".format(self.secondary_phone_number.replace("0", "")))

    @conditionally_run_with_all_backends
    def test_handle_success(self):
        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.phi.location_id)
        payload_generator = RegisterPatientPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(201, {"success": "hooray"}), cases[self.episode_id], None)
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_registered'),
            'true'
        )
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_error'),
            ''
        )

    @conditionally_run_with_all_backends
    def test_handle_failure(self):
        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.phi.location_id)
        payload_generator = RegisterPatientPayloadGenerator(None)
        error = {
            "error": "Something went terribly wrong",
        }
        payload_generator.handle_failure(MockResponse(400, error), cases[self.episode_id], None)
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_registered'),
            'false'
        )
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_error'),
            "400: {}".format(error['error'])
        )


class TestUpdatePatientPayloadGenerator(TestPayloadGeneratorBase):

    def _get_actual_payload(self, casedb):
        return UpdatePatientPayloadGenerator(None).get_payload(None, casedb[self.person_id])

    @conditionally_run_with_all_backends
    def test_get_payload(self):
        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.phi.location_id)
        expected_numbers = u"+91{}, +91{}".format(
            self.primary_phone_number.replace("0", ""),
            self.secondary_phone_number.replace("0", "")
        )
        self._assert_payload_equal(cases, expected_numbers)

    @conditionally_run_with_all_backends
    def test_handle_success(self):
        cases = self.create_case_structure()
        self.factory.create_or_update_case(CaseStructure(
            case_id=self.episode_id,
            attrs={
                'create': False,
                'update': {'dots_99_error': 'bad things'},
            },
        ))
        payload_generator = UpdatePatientPayloadGenerator(None)
        payload_generator.handle_success(MockResponse(200, {"success": "hooray"}), cases[self.person_id], None)
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_error'),
            ''
        )

    @conditionally_run_with_all_backends
    def test_handle_failure(self):
        cases = self.create_case_structure()
        payload_generator = UpdatePatientPayloadGenerator(None)
        error = {
            "error": "Something went terribly wrong",
        }
        payload_generator.handle_failure(MockResponse(400, error), cases[self.person_id], None)
        updated_episode_case = CaseAccessors(self.domain).get_case(self.episode_id)
        self.assertEqual(
            updated_episode_case.dynamic_case_properties().get('dots_99_error'),
            "400: {}".format(error['error'])
        )


class TestAdherencePayloadGenerator(TestPayloadGeneratorBase):
    def _get_actual_payload(self, casedb):
        return AdherencePayloadGenerator(None).get_payload(None, casedb['adherence'])

    @conditionally_run_with_all_backends
    def test_get_payload(self):
        date = datetime(2017, 2, 20)
        cases = self.create_case_structure()
        cases['adherence'] = self.create_adherence_cases([date])[0]
        expected_payload = json.dumps(
            {
                "adherence_value": "unobserved_dose",
                "beneficiary_id": "person",
                "adherence_source": "99DOTS",
                "adherence_date": "2017-02-20"
            }
        )
        self.assertEqual(self._get_actual_payload(cases), expected_payload)

    @conditionally_run_with_all_backends
    def test_handle_success(self):
        date = datetime(2017, 2, 20)
        cases = self.create_case_structure()
        cases['adherence'] = self.create_adherence_cases([date])[0]
        adherence_id = cases['adherence'].case_id
        self.factory.create_or_update_case(CaseStructure(
            case_id=adherence_id,
            attrs={
                'create': False,
                'update': {'dots_99_error': 'bad things'},
            },
        ))
        payload_generator = AdherencePayloadGenerator(None)
        payload_generator.handle_success(MockResponse(200, {"success": "hooray"}), cases['adherence'], None)
        updated_adherence_case = CaseAccessors(self.domain).get_case(adherence_id)
        self.assertEqual(
            updated_adherence_case.dynamic_case_properties().get('dots_99_error'),
            ''
        )
        self.assertEqual(
            updated_adherence_case.dynamic_case_properties().get('dots_99_updated'),
            'true'
        )

    @conditionally_run_with_all_backends
    def test_handle_failure(self):
        date = datetime(2017, 2, 20)
        cases = self.create_case_structure()
        cases['adherence'] = self.create_adherence_cases([date])[0]
        adherence_id = cases['adherence'].case_id
        payload_generator = AdherencePayloadGenerator(None)
        error = {
            "error": "Something went terribly wrong",
        }
        payload_generator.handle_failure(MockResponse(400, error), cases['adherence'], None)
        updated_adherence_case = CaseAccessors(self.domain).get_case(adherence_id)
        self.assertEqual(
            updated_adherence_case.dynamic_case_properties().get('dots_99_error'),
            "400: {}".format(error['error'])
        )


class TestTreatmentOutcomePayloadGenerator(TestPayloadGeneratorBase):
    def _get_actual_payload(self, casedb):
        return TreatmentOutcomePayloadGenerator(None).get_payload(None, casedb[self.episode_id])

    @conditionally_run_with_all_backends
    def test_get_payload(self):
        cases = self.create_case_structure()
        cases[self.episode_id] = self.create_case(
            CaseStructure(
                case_id=self.episode_id,
                attrs={
                    "update": {
                        TREATMENT_OUTCOME: 'the_end_of_days',
                        TREATMENT_OUTCOME_DATE: '2017-01-07',
                    },
                }
            )
        )[0]
        expected_payload = json.dumps(
            {
                "beneficiary_id": "person",
                "treatment_outcome": "the_end_of_days",
                "end_date": "2017-01-07"
            }
        )
        self.assertEqual(self._get_actual_payload(cases), expected_payload)
