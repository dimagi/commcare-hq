from __future__ import absolute_import

import json
from datetime import date, datetime

from django.test import TestCase, override_settings

from casexml.apps.case.mock import CaseStructure
from casexml.apps.case.tests.util import delete_all_cases
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from custom.enikshay.case_utils import get_person_locations
from custom.enikshay.const import (
    CURRENT_ADDRESS,
    ENIKSHAY_ID,
    ENROLLED_IN_PRIVATE,
    PERSON_FIRST_NAME,
    PERSON_LAST_NAME,
    TREATMENT_OUTCOME,
    TREATMENT_OUTCOME_DATE,
    TREATMENT_START_DATE,
    TREATMENT_SUPPORTER_FIRST_NAME,
    TREATMENT_SUPPORTER_LAST_NAME,
    WEIGHT_BAND,
)
from custom.enikshay.integrations.ninetyninedots.const import MERM_ID
from custom.enikshay.integrations.ninetyninedots.repeater_generators import (
    AdherencePayloadGenerator,
    RegisterPatientPayloadGenerator,
    TreatmentOutcomePayloadGenerator,
    UpdatePatientPayloadGenerator,
)
from custom.enikshay.tests.utils import (
    ENikshayCaseStructureMixin,
    ENikshayLocationStructureMixin,
)


class MockResponse(object):
    def __init__(self, status_code, json_data):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


class TestPayloadGeneratorBase(ENikshayCaseStructureMixin, ENikshayLocationStructureMixin, TestCase):

    maxDiff = None

    def tearDown(self):
        super(TestPayloadGeneratorBase, self).tearDown()
        delete_all_cases()

    def _get_actual_payload(self, casedb):
        raise NotImplementedError()

    def _assert_payload_contains_subset(self, casedb, expected_numbers=False, sector=u'public'):
        person_case = casedb[self.person_id]
        episode_case = casedb[self.episode_id]
        person_case_properties = person_case.dynamic_case_properties()
        episode_case_properties = episode_case.dynamic_case_properties()
        person_locations = get_person_locations(person_case)
        locations = {
            u"state_code": person_locations.sto,
            u"district_code": person_locations.dto,
            u"tu_code": person_locations.tu,
        }
        if sector == 'public':
            locations.update({
                u"phi_code": person_locations.phi,
            })
        else:
            locations.update({
                u"he_code": person_locations.pcp,
            })

        expected_numbers = u"+91{}, +91{}, +91{}".format(
            self.primary_phone_number.replace("0", ""),
            self.secondary_phone_number.replace("0", ""),
            self.other_number.replace("0", "")
        ) if expected_numbers is False else expected_numbers
        expected_payload = {
            u"beneficiary_id": self.person_id,
            u"enikshay_id": person_case_properties.get(ENIKSHAY_ID, None),
            u"first_name": person_case_properties.get(PERSON_FIRST_NAME, None),
            u"last_name": person_case_properties.get(PERSON_LAST_NAME, None),
            u"phone_numbers": expected_numbers,
            u"treatment_start_date": episode_case_properties.get(TREATMENT_START_DATE, None),
            u"treatment_supporter_name": u"{} {}".format(
                episode_case_properties.get(TREATMENT_SUPPORTER_FIRST_NAME, ''),
                episode_case_properties.get(TREATMENT_SUPPORTER_LAST_NAME, ''),
            ),
            u"treatment_supporter_phone_number": u"+91{}".format(self.treatment_supporter_phone[1:]),
            u"weight_band": episode_case_properties.get(WEIGHT_BAND),
            u"address": person_case_properties.get(CURRENT_ADDRESS),
            u"sector": sector,
        }
        if episode_case_properties.get(MERM_ID, None) is not None:
            expected_payload.update({
                u"merm_params": {
                    u"IMEI": episode_case_properties.get(MERM_ID, None),
                }
            })
        expected_payload.update(locations)
        actual_payload = json.loads(self._get_actual_payload(casedb))
        self.assertDictContainsSubset(expected_payload, actual_payload)
        return actual_payload


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class TestRegisterPatientPayloadGenerator(TestPayloadGeneratorBase):

    def _get_actual_payload(self, casedb):
        return RegisterPatientPayloadGenerator(None).get_payload(None, casedb[self.episode_id])

    def test_get_payload(self):
        del self.episode.attrs['update']['merm_id']
        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.phi.location_id)
        self._assert_payload_contains_subset(cases)

    def test_get_payload_no_numbers(self):
        self.primary_phone_number = None
        self.secondary_phone_number = None
        self.other_number = None
        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.phi.location_id)
        self._assert_payload_contains_subset(cases, None)

    def test_get_payload_secondary_number_only(self):
        self.primary_phone_number = None
        self.other_number = None
        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.phi.location_id)
        self._assert_payload_contains_subset(cases, u"+91{}".format(self.secondary_phone_number.replace("0", "")))

    def test_get_payload_private_sector(self):
        self.person.attrs['update'][ENROLLED_IN_PRIVATE] = 'true'
        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.pcp.location_id)
        self._assert_payload_contains_subset(cases, sector='private')

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

    def test_get_payload_valid_checkbox(self):
        self.occurrence.attrs['update']['key_populations'] = 'urban_slum tobacco'  # test checkbox type
        self._test_checkbox_type()

    def test_get_payload_invalid_checkbox(self):
        self.occurrence.attrs['update']['key_populations'] = 'foo bar'
        with self.assertRaises(ValueError):
            self._test_checkbox_type()

    def _test_checkbox_type(self):

        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.phi.location_id)

        expected_numbers = u"+91{}, +91{}, +91{}".format(
            self.primary_phone_number.replace("0", ""),
            self.secondary_phone_number.replace("0", ""),
            self.other_number.replace("0", "")
        )
        payload = self._assert_payload_contains_subset(cases, expected_numbers)

        self.assertTrue('key_populations' in payload)
        self.assertEqual(payload['key_populations'], 'urban_slum tobacco')

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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class TestUpdatePatientPayloadGenerator(TestPayloadGeneratorBase):

    def _get_actual_payload(self, casedb):
        return UpdatePatientPayloadGenerator(None).get_payload(None, casedb[self.person_id])

    def test_get_payload(self):
        self.person.attrs['update']['language_code'] = ''
        cases = self.create_case_structure()
        cases[self.person_id] = self.assign_person_to_location(self.phi.location_id)
        expected_numbers = u"+91{}, +91{}, +91{}".format(
            self.primary_phone_number.replace("0", ""),
            self.secondary_phone_number.replace("0", ""),
            self.other_number.replace("0", "")
        )
        payload = self._assert_payload_contains_subset(cases, expected_numbers)
        self.assertFalse('language_code' in payload)

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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class TestAdherencePayloadGenerator(TestPayloadGeneratorBase):
    def _get_actual_payload(self, casedb):
        return AdherencePayloadGenerator(None).get_payload(None, casedb['adherence'])

    def test_get_payload(self):
        cases = self.create_case_structure()
        cases['adherence'] = self.create_adherence_cases([date(2017, 2, 20)])[0]
        expected_payload = json.dumps(
            {
                "adherence_value": "unobserved_dose",
                "beneficiary_id": "person",
                "adherence_source": "99DOTS",
                "adherence_date": "2017-02-20"
            }
        )
        self.assertEqual(self._get_actual_payload(cases), expected_payload)

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


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True, SERVER_ENVIRONMENT='enikshay')
class TestTreatmentOutcomePayloadGenerator(TestPayloadGeneratorBase):
    def _get_actual_payload(self, casedb):
        return TreatmentOutcomePayloadGenerator(None).get_payload(None, casedb[self.episode_id])

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
