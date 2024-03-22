import dataclasses
import uuid
from dataclasses import dataclass
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase

from abdm_integrator.const import HealthInformationType, IdentifierType
from abdm_integrator.hip.exceptions import (
    DiscoveryMultiplePatientsFoundError,
    DiscoveryNoPatientFoundError,
)
from abdm_integrator.hip.views.care_contexts import PatientDetails

from corehq.apps.es import case_search_adapter
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.pillows.case_search import CaseSearchReindexerFactory
from corehq.util.test_utils import create_and_save_a_case
from custom.abdm.discovery_request import (
    ABHA_NUMBER_PROPERTY,
    CARE_CONTEXT_CASE_TYPE,
    DATE_OF_BIRTH_PROPERTY,
    GENDER_PROPERTY,
    HEALTH_ID_PROPERTY,
    HIP_ID_PROPERTY,
    PATIENT_CASE_TYPE,
    PHONE_NUMBER_PROPERTY,
    discover_patient_with_care_contexts,
)


@dataclass(frozen=True)
class PatientInfo:
    name: str
    gender: str = None
    date_of_birth: str = None
    mobile: str = None
    health_id: str = None
    abha_number: str = None


@es_test(requires=[case_search_adapter])
@patch('custom.abdm.discovery_request.find_domains_with_toggle_enabled',
       return_value=['abdm_domain_1', 'abdm_domain_2'])
class TestDiscoveryRequest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_1 = 'abdm_domain_1'
        cls.domain_2 = 'abdm_domain_2'
        cls.hip_1 = 'test_hip_1'
        cls.hip_2 = 'test_hip_2'

    def setUp(self):
        super().setUp()
        self.clean_up_cases = []

        self.patient_1 = PatientInfo(name='health_id_discover', health_id='health_id_discover@sbx')
        self.patient_1_cases = self._add_patient_with_health_records(self.domain_1, self.hip_1, self.patient_1, 2)
        self._add_to_cleanup(self.patient_1_cases)

        self.patient_2 = PatientInfo(
            name='demographics_discover',
            gender='female',
            mobile='9988776655',
            date_of_birth='2011-11-11'
        )
        self.patient_2_cases = self._add_patient_with_health_records(self.domain_1, self.hip_1, self.patient_2, 2)
        self._add_to_cleanup(self.patient_2_cases)

    def _add_to_cleanup(self, patient_cases):
        self.clean_up_cases.extend([patient_cases[0], patient_cases[1]] + patient_cases[2])

    def tearDown(self):
        for case in self.clean_up_cases:
            case.delete()
        self.clean_up_cases.clear()
        super(TestDiscoveryRequest, self).tearDown()

    @classmethod
    def _add_patient_with_health_records(cls, domain, hip_id, patient_info, health_records_count=0):
        patient_case = cls._add_patient_case(domain, patient_info.name)
        parent_index = {'parent': ('patient', patient_case.case_id)}
        patient_abdm_case = cls._add_abdm_patient_case(domain, hip_id, patient_info, parent_index)
        health_records_cases = []
        for count in range(health_records_count):
            health_records_cases.append(
                cls._add_abdm_care_context_case(
                    domain,
                    hip_id,
                    patient_info.health_id,
                    parent_index
                )
            )
        return patient_case, patient_abdm_case, health_records_cases

    @classmethod
    def _add_patient_case(cls, domain, name):
        return cls._create_case_and_sync_to_es(
            domain,
            name,
            'patient',
            case_properties={}
        )

    @classmethod
    def _add_abdm_patient_case(cls, domain, hip_id, patient_info, index=None):
        case_properties = {
            HIP_ID_PROPERTY: hip_id,
            HEALTH_ID_PROPERTY: patient_info.health_id,
            PHONE_NUMBER_PROPERTY: patient_info.mobile,
            DATE_OF_BIRTH_PROPERTY: patient_info.date_of_birth,
            GENDER_PROPERTY: patient_info.gender,
            ABHA_NUMBER_PROPERTY: patient_info.abha_number,
        }
        return cls._create_case_and_sync_to_es(
            domain,
            patient_info.name,
            PATIENT_CASE_TYPE,
            case_properties,
            index=index
        )

    @classmethod
    def _add_abdm_care_context_case(cls, domain, hip_id, health_id, index=None):
        case_id = uuid.uuid4().hex
        case_name = f'Visit for {datetime.utcnow().isoformat()}'
        case_properties = {
            HIP_ID_PROPERTY: hip_id,
            HEALTH_ID_PROPERTY: health_id,
            'domain': domain,
            'fhir_care_context_reference': case_id,
            'all_hi_types': HealthInformationType.PRESCRIPTION,
            'fhir_care_context_label': case_name,
        }
        return cls._create_case_and_sync_to_es(
            domain,
            case_name,
            CARE_CONTEXT_CASE_TYPE,
            case_properties,
            case_id,
            index=index,
            close=True
        )

    @staticmethod
    def _create_case_and_sync_to_es(domain, case_name, case_type, case_properties, case_id=None, index=None,
                                    close=False):
        case_id = case_id or uuid.uuid4().hex
        case = create_and_save_a_case(
            domain,
            case_id,
            case_name,
            case_properties=case_properties,
            case_type=case_type,
            index=index
        )
        case.opened_on = datetime.utcnow()
        case.save()
        if close:
            case.close = True
            case.closed_on = datetime.utcnow()
            case.save()
        CaseSearchReindexerFactory(domain=domain).build().reindex()
        manager.index_refresh(case_search_adapter.index_name)
        return case

    @staticmethod
    def _get_care_context_case_by_reference(care_context_cases, reference):
        return next(case for case in care_context_cases if case.case_id == reference)

    def _assert_care_contexts_result(self, care_contexts_results, care_context_cases):
        for care_context in care_contexts_results:
            care_context_case = self._get_care_context_case_by_reference(
                care_context_cases,
                care_context['referenceNumber']
            )
            self.assertIsNotNone(care_context_case)
            self.assertEqual(
                care_context,
                {
                    'referenceNumber': care_context_case.case_id,
                    'display': care_context_case.name,
                    'hiTypes': care_context_case.case_json['all_hi_types'].split(','),
                    'additionalInfo': {
                        'domain': care_context_case.domain,
                        'record_date': care_context_case.closed_on.isoformat()
                    }
                }
            )

    def test_discover_by_health_id_success(self, *args):
        requested_patient = PatientDetails(
            id=self.patient_1.health_id,
            name=self.patient_1.name,
            health_id=self.patient_1.health_id,
            gender='male',
            year_of_birth=2000
        )

        result = discover_patient_with_care_contexts(requested_patient, self.hip_1)

        self.assertEqual(result['matchedBy'], [IdentifierType.HEALTH_ID])
        self.assertEqual(result['referenceNumber'], self.patient_1_cases[0].case_id)
        self.assertEqual(result['display'], self.patient_1_cases[1].name)
        self.assertEqual(len(result['careContexts']), 2)
        self._assert_care_contexts_result(result['careContexts'], self.patient_1_cases[2])

    def test_discover_by_health_id_no_health_records(self, *args):
        patient_info = PatientInfo(name='test_2', health_id='test2@sbx')
        new_patient_cases = self._add_patient_with_health_records(self.domain_1, self.hip_1, patient_info)
        self._add_to_cleanup(new_patient_cases)

        requested_patient = PatientDetails(
            id=patient_info.health_id,
            name=patient_info.name,
            health_id=patient_info.health_id,
            gender='male',
            year_of_birth=2000
        )

        result = discover_patient_with_care_contexts(requested_patient, self.hip_1)

        self.assertEqual(result['matchedBy'], [IdentifierType.HEALTH_ID])
        self.assertEqual(result['referenceNumber'], new_patient_cases[0].case_id)
        self.assertEqual(result['display'], new_patient_cases[1].name)
        self.assertEqual(len(result['careContexts']), 0)

    def test_discover_by_health_id_multiple_patients(self, *args):
        patient_info = PatientInfo(name='health_id_discover_2', health_id=self.patient_1.health_id)
        new_patient_cases = self._add_patient_with_health_records(
            self.domain_1,
            self.hip_1,
            patient_info,
            health_records_count=1
        )
        self._add_to_cleanup(new_patient_cases)

        requested_patient = PatientDetails(
            id=self.patient_1.health_id,
            name=self.patient_1.name,
            health_id=self.patient_1.health_id,
            gender='male',
            year_of_birth=2000
        )

        result = discover_patient_with_care_contexts(requested_patient, self.hip_1)

        self.assertEqual(result['matchedBy'], [IdentifierType.HEALTH_ID])
        self.assertEqual(result['referenceNumber'], self.patient_1_cases[0].case_id)
        self.assertEqual(result['display'], self.patient_1_cases[1].name)
        self.assertEqual(len(result['careContexts']), 3)
        self._assert_care_contexts_result(result['careContexts'], self.patient_1_cases[2] + new_patient_cases[2])

    def test_discover_by_demographics_success(self, *args):
        requested_patient = PatientDetails(
            id='demographics_discover@sbx',
            name='demographics_discover',
            health_id='demographics_discover@sbx',
            gender=self.patient_2.gender,
            year_of_birth=2010,
            mobile=self.patient_2.mobile
        )

        result = discover_patient_with_care_contexts(requested_patient, self.hip_1)

        self.assertEqual(result['matchedBy'], [IdentifierType.MOBILE])
        self.assertEqual(result['referenceNumber'], self.patient_2_cases[0].case_id)
        self.assertEqual(result['display'], self.patient_2_cases[1].name)
        self.assertEqual(len(result['careContexts']), 2)
        self._assert_care_contexts_result(result['careContexts'], self.patient_2_cases[2])

    def test_discover_by_demographics_no_health_records(self, *args):
        patient_info = PatientInfo(name='test2', gender='female', mobile='9988776655', date_of_birth='2011-11-11')
        new_patient_cases = self._add_patient_with_health_records(self.domain_2, self.hip_1, patient_info)
        self._add_to_cleanup(new_patient_cases)

        requested_patient = PatientDetails(
            id='test2@sbx',
            name='test2',
            health_id='test2@sbx',
            gender=patient_info.gender,
            year_of_birth=2010,
            mobile=patient_info.mobile
        )

        result = discover_patient_with_care_contexts(requested_patient, self.hip_1)

        self.assertEqual(result['matchedBy'], [IdentifierType.MOBILE])
        self.assertEqual(result['referenceNumber'], new_patient_cases[0].case_id)
        self.assertEqual(result['display'], new_patient_cases[1].name)
        self.assertEqual(len(result['careContexts']), 0)

    def test_discover_by_demographics_multiple_patients_same_name_and_dob(self, *args):
        patient_info = dataclasses.replace(self.patient_2)
        new_patient_cases = self._add_patient_with_health_records(self.domain_1, self.hip_1, patient_info, 1)
        self._add_to_cleanup(new_patient_cases)

        requested_patient = PatientDetails(
            id='demographics_discover@sbx',
            name=patient_info.name,
            health_id='demographics_discover@sbx',
            gender=patient_info.gender,
            year_of_birth=2010,
            mobile=patient_info.mobile
        )

        result = discover_patient_with_care_contexts(requested_patient, self.hip_1)

        self.assertEqual(result['matchedBy'], [IdentifierType.MOBILE])
        self.assertEqual(result['referenceNumber'], self.patient_2_cases[0].case_id)
        self.assertEqual(result['display'], self.patient_2_cases[1].name)
        self.assertEqual(len(result['careContexts']), 3)
        self._assert_care_contexts_result(result['careContexts'], self.patient_2_cases[2] + new_patient_cases[2])

    def test_discover_by_demographics_multiple_patients_error(self, *args):
        patient_info = PatientInfo(
            name='demographics_discover_2',
            gender=self.patient_2.gender,
            mobile=self.patient_2.mobile,
            date_of_birth=self.patient_2.date_of_birth
        )
        new_patient_cases = self._add_patient_with_health_records(self.domain_1, self.hip_1, patient_info, 1)
        self._add_to_cleanup(new_patient_cases)

        requested_patient = PatientDetails(
            id='demographics_discover@sbx',
            name='demographics_discover',
            health_id='demographics_discover@sbx',
            gender=patient_info.gender,
            year_of_birth=2010,
            mobile=patient_info.mobile
        )

        with self.assertRaises(DiscoveryMultiplePatientsFoundError):
            discover_patient_with_care_contexts(requested_patient, self.hip_1)

    def test_discover_no_patient_found(self, *args):
        requested_patient = PatientDetails(
            id='does_not_exist@sbx',
            name='does_not_exist',
            health_id='does_not_exist@sbx',
            gender='female',
            year_of_birth=2010,
            mobile='1122334455'
        )

        with self.assertRaises(DiscoveryNoPatientFoundError):
            discover_patient_with_care_contexts(requested_patient, self.hip_1)

    def test_discover_no_patient_found_in_different_hip(self, *args):
        requested_patient = PatientDetails(
            id='health_id_discover@sbx',
            name='health_id_discover',
            health_id='health_id_discover@sbx',
            gender='male',
            year_of_birth=2000,
            mobile='1122334455'
        )

        with self.assertRaises(DiscoveryNoPatientFoundError):
            discover_patient_with_care_contexts(requested_patient, self.hip_2)

    def test_discover_by_health_id_same_hip_id_across_domains(self, *args):
        new_patient_cases = self._add_patient_with_health_records(
            self.domain_2,
            self.hip_1,
            self.patient_1,
            health_records_count=1
        )
        self._add_to_cleanup(new_patient_cases)

        requested_patient = PatientDetails(
            id='health_id_discover@sbx',
            name='health_id_discover',
            health_id='health_id_discover@sbx',
            gender='M',
            year_of_birth=2000
        )

        result = discover_patient_with_care_contexts(requested_patient, self.hip_1)

        self.assertEqual(result['matchedBy'], [IdentifierType.HEALTH_ID])
        self.assertEqual(result['referenceNumber'], self.patient_1_cases[0].case_id)
        self.assertEqual(result['display'], self.patient_1_cases[1].name)
        self.assertEqual(len(result['careContexts']), 3)
        self._assert_care_contexts_result(result['careContexts'], self.patient_1_cases[2] + new_patient_cases[2])

    def test_discover_by_demographics_same_hip_id_across_domains(self, *args):
        patient_info = dataclasses.replace(self.patient_2)
        new_patient_cases = self._add_patient_with_health_records(self.domain_2, self.hip_1, patient_info, 1)
        self._add_to_cleanup(new_patient_cases)

        requested_patient = PatientDetails(
            id='demographics_discover@sbx',
            name='demographics_discover',
            health_id='demographics_discover@sbx',
            gender='female',
            year_of_birth=2010,
            mobile='9988776655'
        )

        result = discover_patient_with_care_contexts(requested_patient, self.hip_1)

        self.assertEqual(result['matchedBy'], [IdentifierType.MOBILE])
        self.assertEqual(result['referenceNumber'], self.patient_2_cases[0].case_id)
        self.assertEqual(result['display'], self.patient_2_cases[1].name)
        self.assertEqual(len(result['careContexts']), 3)
        self._assert_care_contexts_result(result['careContexts'], self.patient_2_cases[2] + new_patient_cases[2])
