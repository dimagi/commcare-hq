from datetime import datetime, timezone

from django.conf import settings

from corehq.form_processor.models import CommCareCase
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.fhir.models import FHIRResourceType, build_fhir_resource
from custom.abdm.fhir.clinical_artifacts import (
    ABDM_FHIR_VERSION,
    FHIRConfigErrorMessage,
    FHIRConfigValidationError,
    artifact_from_health_information_type,
    validate_fhir_configuration_for_artifact,
    validate_mandatory_case_types_for_artifact,
)

UUID_URN_PREFIX = "urn:uuid:"


def fhir_resources_configured_for_domain(domain):
    return list(
        FHIRResourceType.objects.filter(domain=domain, fhir_version=ABDM_FHIR_VERSION)
    )


def fetch_related_cases(domain, care_context_reference, case_types):
    return CommCareCase.objects.get_reverse_indexed_cases(
        domain, [care_context_reference], case_types=case_types
    )


def get_medication_request_cases_for_condition(domain, cases, resource_type_to_case_type):
    # Medication Request cases are set as related cases for condition due to one to many mapping
    condition_case_ids = [case.case_id for case in cases if case.type == resource_type_to_case_type["Condition"]]
    return CommCareCase.objects.get_reverse_indexed_cases(
        domain, condition_case_ids, [resource_type_to_case_type["MedicationRequest"]]
    )


def get_resource_type_from_case_type(case_type_name, resource_type_to_case_type):
    return next(
        resource_type for resource_type, case_type in resource_type_to_case_type.items()
        if case_type == case_type_name
    )


def cases_as_fhir_entries(cases, resource_type_to_case_type):
    entries = {}
    for case in cases:
        try:
            fhir_data = build_fhir_resource(case, ABDM_FHIR_VERSION)
            resource_type = get_resource_type_from_case_type(case.type, resource_type_to_case_type)
            entries.setdefault(resource_type, []).append(fhir_data)
        except ConfigurationError as err:
            raise FHIRConfigValidationError(f"{FHIRConfigErrorMessage.DATA_DICT_FHIR_CONFIG} {str(err)}")
    return entries


class ABDMDocumentBundleGenerator:

    def __init__(self, care_context_reference, clinical_artifact, fhir_entries):
        self.care_context_reference = care_context_reference
        self.clinical_artifact = clinical_artifact
        self.fhir_entries = fhir_entries

    @staticmethod
    def generate_reference_from_resource(resource):
        return {
            "type": resource["resourceType"],
            "reference": f"{UUID_URN_PREFIX}{resource['id']}"
        }

    def _get_subject_resource(self):
        subject_resource = self.fhir_entries[self.clinical_artifact.SUBJECT][0]
        return self.generate_reference_from_resource(subject_resource)

    def _get_author_resource(self):
        # First resource type from the list that is configured is considered here as author
        author_resource_type = next(
            resource for resource in self.clinical_artifact.AUTHOR_CHOICES
            if resource in self.fhir_entries.keys()
        )
        author_resource = self.fhir_entries[author_resource_type][0]
        return [self.generate_reference_from_resource(author_resource)]

    def _generate_section(self):
        section = [{
            "title": self.clinical_artifact.TEXT,
            "code": {
                "coding": self.clinical_artifact.coding()
            },
            "entry": []
        }]
        for resource_type in self.clinical_artifact.SECTION_ENTRY_CHOICES:
            for resource in self.fhir_entries.get(resource_type, []):
                section[0]["entry"].append(self.generate_reference_from_resource(resource))
        return section

    def generate_composition(self):
        composition = {
            "resourceType": "Composition",
            "title": self.clinical_artifact.TEXT,
            "id": self.care_context_reference,
            "status": "final",
            "date": datetime.now(timezone.utc).isoformat(),
            "subject": self._get_subject_resource(),
            "author": self._get_author_resource(),
            "type": {
                "coding": self.clinical_artifact.coding(),
                "text": self.clinical_artifact.TEXT
            }
        }
        if "Encounter" in self.fhir_entries.keys():
            composition["encounter"] = self.generate_reference_from_resource(self.fhir_entries["Encounter"][0])
        composition["section"] = self._generate_section()
        return composition

    def generate_bundle_entries(self, composition):
        entries = [{
            "resource": composition,
            "fullUrl": f"{UUID_URN_PREFIX}{composition['id']}"
        }]
        for resource_type in self.clinical_artifact.BUNDLE_ENTRIES:
            for resource in self.fhir_entries.get(resource_type, []):
                entries.append({
                    "resource": resource,
                    "fullUrl": f"{UUID_URN_PREFIX}{resource['id']}"
                })
        return entries

    def generate(self):
        composition = self.generate_composition()
        bundle = {
            "resourceType": "Bundle",
            "type": "document",
            "id": f"Bundle-{self.care_context_reference}",
            "timestamp": composition["date"],
            "meta": {
                "versionId": "1"
            },
            "identifier": {
                "system": f"https://{settings.SERVER_ENVIRONMENT}.commcare.org",
                "value": self.care_context_reference
            },
            "entry": self.generate_bundle_entries(composition)
        }
        return bundle


def fhir_health_data_from_hq(care_context_reference, health_information_types, domain):
    """
    Returns FHIR Health data as a document bundle for a particular care context reference.
    Utilises Data Dictionary Setup for creating fhir entries for individual resources.
    Utilises ABDM Clinical Artifact definition for creating document bundle of fhir entries.
    """
    applicable_resource_types = set()
    configured_resource_types = fhir_resources_configured_for_domain(domain)

    for health_information_type in health_information_types:
        clinical_artifact = artifact_from_health_information_type(health_information_type)
        if clinical_artifact is None:
            raise FHIRConfigValidationError(
                FHIRConfigErrorMessage.HEALTH_INFORMATION_NOT_SUPPORTED.format(
                    health_information_type=health_information_type
                )
            )
        validate_fhir_configuration_for_artifact(
            clinical_artifact, [resource_type.name for resource_type in configured_resource_types]
        )
        applicable_resource_types.update(
            {
                resource_type for resource_type in configured_resource_types
                if resource_type.name in clinical_artifact.BUNDLE_ENTRIES
            }
        )

    resource_type_to_case_type = {resource_type.name: resource_type.case_type.name
                                  for resource_type in applicable_resource_types}
    cases = fetch_related_cases(domain, care_context_reference, list(resource_type_to_case_type.values()))
    if not cases:
        return []

    if resource_type_to_case_type.get("Condition") and resource_type_to_case_type.get("MedicationRequest"):
        cases.extend(get_medication_request_cases_for_condition(domain, cases, resource_type_to_case_type))

    fhir_entries = cases_as_fhir_entries(cases, resource_type_to_case_type)

    fhir_data = []
    for health_information_type in health_information_types:
        clinical_artifact = artifact_from_health_information_type(health_information_type)
        validate_mandatory_case_types_for_artifact(clinical_artifact, list(fhir_entries.keys()))
        fhir_data.append(
            ABDMDocumentBundleGenerator(care_context_reference, clinical_artifact, fhir_entries).generate()
        )
    return fhir_data
