import uuid
from copy import deepcopy
from dataclasses import dataclass

from django.conf import settings
from django.test import TestCase

from abdm_integrator.const import HealthInformationType

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import delete_all_cases

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.models import CommCareCaseIndex
from corehq.motech.fhir.tests.utils import (
    add_case_property_with_resource_property_path,
    add_case_type_with_resource_type,
)
from custom.abdm.fhir.clinical_artifacts import (
    FHIRConfigErrorMessage,
    FHIRConfigValidationError,
    FHIRMissingCasesError,
    PrescriptionRecord,
)
from custom.abdm.fhir.document_bundle import (
    UUID_URN_PREFIX,
    fhir_health_data_from_hq,
)


@dataclass()
class FHIRDataDict:
    case_type: str
    resource_type: str
    properties_map: dict


@dataclass()
class FHIRCaseData:
    case_type: str
    properties: dict


CARE_CONTEXT_CASE_TYPE = "fhir_care_context"
PATIENT_CASE_TYPE = "fhir_patient_data"
PRACTITIONER_CASE_TYPE = "fhir_practitioner_data"
MEDICATION_REQUEST_CASE_TYPE = "fhir_medication_request_data"

FHIR_DATA_DICT_CONFIG = [
    FHIRDataDict(PATIENT_CASE_TYPE, "Patient", {"name": "$.name[0].text"}),
    FHIRDataDict(PRACTITIONER_CASE_TYPE, "Practitioner", {"name": "$.name[0].text"}),
    FHIRDataDict(
        "fhir_medication_request_data",
        "MedicationRequest",
        {"subject_display": "$.subject.display", "subject_reference": "$.subject.reference"}),
]
FHIR_CASES_DATA = [
    FHIRCaseData(PATIENT_CASE_TYPE, {"name": "Bob"}),
    FHIRCaseData(PRACTITIONER_CASE_TYPE, {"name": "John"}),
    FHIRCaseData(
        MEDICATION_REQUEST_CASE_TYPE,
        {"subject_display": "Medicine", "subject_reference": "Reference"}
    ),
]


class TestFHIRHealthDataFromHQ(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = "abdm-fhir-bundle"
        cls.care_context_case_id = uuid.uuid4().hex
        cls.domain_obj = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def tearDown(self):
        delete_all_cases()
        super().tearDown()

    @staticmethod
    def _get_caseblock(case_id, case_type, updates=None):
        return CaseBlock(create=True, case_id=case_id, case_type=case_type, update=updates)

    @staticmethod
    def _get_case_by_case_type(cases, case_type):
        return next((case for case in cases if case.type == case_type), None)

    @classmethod
    def _setup_cases(cls, fhir_cases_data):
        cases_block = [cls._get_caseblock(cls.care_context_case_id, CARE_CONTEXT_CASE_TYPE,).as_text()]
        for case_data in fhir_cases_data:
            cases_block.append(
                cls._get_caseblock(uuid.uuid4().hex, case_data.case_type, case_data.properties).as_text()
            )
        _, cases = submit_case_blocks(cases_block, cls.domain)
        for case_data in fhir_cases_data:
            case = cls._get_case_by_case_type(cases, case_data.case_type)
            case.track_create(CommCareCaseIndex(
                case=case,
                identifier="parent",
                referenced_type=CARE_CONTEXT_CASE_TYPE,
                referenced_id=cls.care_context_case_id,
                relationship_id=CommCareCaseIndex.CHILD
            ))
            case.save(with_tracked_models=True)
        return cases

    @staticmethod
    def _get_entry_by_resource_type(entries, resource_type):
        return next((entry for entry in entries if entry["resource"]["resourceType"] == resource_type), None)

    @classmethod
    def _setup_fhir_data_dict(cls, fhir_data_dict_config):
        for config in fhir_data_dict_config:
            case_type, resource_type = add_case_type_with_resource_type(
                cls.domain,
                config.case_type,
                config.resource_type
            )
            for property_name, value in config.properties_map.items():
                add_case_property_with_resource_property_path(case_type, property_name, resource_type, value)

    def test_fhir_health_data_from_hq_health_info_type_not_supported(self):
        self._setup_fhir_data_dict(FHIR_DATA_DICT_CONFIG)
        self._setup_cases(FHIR_CASES_DATA)
        health_information_type = "invalid"
        with self.assertRaises(FHIRConfigValidationError) as error:
            fhir_health_data_from_hq(self.care_context_case_id, [health_information_type], self.domain)
        self.assertEqual(
            str(error.exception),
            FHIRConfigErrorMessage.HEALTH_INFORMATION_NOT_SUPPORTED.format(
                health_information_type=health_information_type
            )
        )

    def test_fhir_health_data_from_hq_missing_data_dict_config(self):
        self._setup_cases(FHIR_CASES_DATA)
        with self.assertRaises(FHIRConfigValidationError) as error:
            fhir_health_data_from_hq(self.care_context_case_id, [HealthInformationType.PRESCRIPTION], self.domain)
        self.assertEqual(
            str(error.exception),
            FHIRConfigErrorMessage.SUBJECT_CONFIG_ABSENT.format(
                subject=PrescriptionRecord.SUBJECT,
                artifact=PrescriptionRecord
            )
        )

    def test_fhir_health_data_from_hq_fhir_configuration_error(self):
        updated_fhir_data_dict_config = deepcopy(FHIR_DATA_DICT_CONFIG)
        updated_fhir_data_dict_config[2].properties_map = {}
        self._setup_fhir_data_dict(updated_fhir_data_dict_config)
        self._setup_cases(FHIR_CASES_DATA)
        with self.assertRaises(FHIRConfigValidationError) as error:
            fhir_health_data_from_hq(self.care_context_case_id, [HealthInformationType.PRESCRIPTION], self.domain)
        self.assertTrue(str(error.exception).startswith(FHIRConfigErrorMessage.DATA_DICT_FHIR_CONFIG))

    def test_fhir_health_data_from_hq_missing_mandatory_cases(self):
        self._setup_fhir_data_dict(FHIR_DATA_DICT_CONFIG)
        updated_fhir_cases_data = deepcopy(FHIR_CASES_DATA)
        updated_fhir_cases_data.pop()
        self._setup_cases(updated_fhir_cases_data)
        with self.assertRaises(FHIRMissingCasesError) as error:
            fhir_health_data_from_hq(self.care_context_case_id, [HealthInformationType.PRESCRIPTION], self.domain)
        self.assertEqual(
            str(error.exception),
            FHIRConfigErrorMessage.SECTION_ENTRY_CASE_ABSENT.format(artifact=PrescriptionRecord)
        )

    def test_fhir_health_data_from_hq_no_records_present(self):
        self._setup_fhir_data_dict(FHIR_DATA_DICT_CONFIG)
        self._setup_cases(FHIR_CASES_DATA)
        result = fhir_health_data_from_hq("does-not-exist", [HealthInformationType.PRESCRIPTION], self.domain)
        self.assertEqual(result, [])

    def test_fhir_health_data_from_hq_success(self):
        self._setup_fhir_data_dict(FHIR_DATA_DICT_CONFIG)
        cases = self._setup_cases(FHIR_CASES_DATA)

        result = fhir_health_data_from_hq(
            self.care_context_case_id,
            [HealthInformationType.PRESCRIPTION],
            self.domain
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(len(result[0]["entry"]), len(FHIR_CASES_DATA) + 1)
        self.assertEqual(result[0]["resourceType"], "Bundle")
        self.assertEqual(result[0]["type"], "document")
        self.assertEqual(result[0]["id"], f"Bundle-{self.care_context_case_id}")
        self.assertEqual(result[0]["identifier"], {
            "system": f"https://{settings.SERVER_ENVIRONMENT}.commcare.org",
            "value": self.care_context_case_id
        })

        patient_case = self._get_case_by_case_type(cases, PATIENT_CASE_TYPE)
        expected_patient_entry = {
            "resource": {
                "name": [{"text": FHIR_CASES_DATA[0].properties["name"]}],
                "id": patient_case.case_id,
                "resourceType": "Patient"
            },
            "fullUrl": f"{UUID_URN_PREFIX}{patient_case.case_id}"
        }
        patient_entry = self._get_entry_by_resource_type(result[0]["entry"], "Patient")
        self.assertEqual(patient_entry, expected_patient_entry)

        practitioner_case = self._get_case_by_case_type(cases, PRACTITIONER_CASE_TYPE)
        expected_practitioner_entry = {
            "resource": {
                "name": [{"text": FHIR_CASES_DATA[1].properties["name"]}],
                "id": practitioner_case.case_id,
                "resourceType": "Practitioner"
            },
            "fullUrl": f"{UUID_URN_PREFIX}{practitioner_case.case_id}"
        }
        practitioner_entry = self._get_entry_by_resource_type(result[0]["entry"], "Practitioner")
        self.assertEqual(practitioner_entry, expected_practitioner_entry)

        medication_request_case = self._get_case_by_case_type(cases, MEDICATION_REQUEST_CASE_TYPE)
        expected_medication_request_entry = {
            "resource": {
                "subject": {
                    "display": FHIR_CASES_DATA[2].properties["subject_display"],
                    "reference": FHIR_CASES_DATA[2].properties["subject_reference"]
                },
                "id": medication_request_case.case_id,
                "resourceType": "MedicationRequest"
            },
            "fullUrl": f"{UUID_URN_PREFIX}{medication_request_case.case_id}"
        }
        medication_request_entry = self._get_entry_by_resource_type(result[0]["entry"], "MedicationRequest")
        self.assertEqual(medication_request_entry, expected_medication_request_entry)

        expected_composition_entry = {
            "resource": {
                "resourceType": "Composition",
                "title": PrescriptionRecord.TEXT,
                "id": self.care_context_case_id,
                "status": "final",
                "subject": {
                    "type": "Patient",
                    "reference": f"{UUID_URN_PREFIX}{patient_case.case_id}"
                },
                "author": [
                    {
                        "type": "Practitioner",
                        "reference": f"{UUID_URN_PREFIX}{practitioner_case.case_id}"
                    }
                ],
                "type": {
                    "coding": PrescriptionRecord.coding(),
                    "text": PrescriptionRecord.TEXT
                },
                "section": [
                    {
                        "title": PrescriptionRecord.TEXT,
                        "code": {
                            "coding": PrescriptionRecord.coding()
                        },
                        "entry": [
                            {
                                "type": "MedicationRequest",
                                "reference": f"{UUID_URN_PREFIX}{medication_request_case.case_id}"
                            }
                        ]
                    }
                ]
            },
            "fullUrl": f"{UUID_URN_PREFIX}{self.care_context_case_id}"
        }
        composition_entry = self._get_entry_by_resource_type(result[0]["entry"], "Composition")
        del composition_entry["resource"]["date"]
        self.assertEqual(composition_entry, expected_composition_entry)
