from datetime import datetime, timezone

from corehq.form_processor.models import CommCareCase
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.fhir.models import FHIRResourceType, build_fhir_resource
from custom.abdm.const import HealthInformationType
from custom.abdm.fhir.clinical_artifacts import artifact_from_health_information_type, validate_fhir_resources_config


# TODO Check if fhir client lib is worth using here
# TODO Check if any of methods is relevant moving to motech fhir
# TODO Decide on how to set HI Type for Care Context Reference (maybe while LINKING)
# TODO Refactoring and Error Handling as applicable

def fhir_resources_configured_for_domain(domain):
    return list(FHIRResourceType.objects.filter(
        domain=domain, fhir_version=ABDM_FHIR_VERSION
    ))


def fetch_related_cases(domain, care_context_reference, case_types_for_resource_types):
    return CommCareCase.objects.get_reverse_indexed_cases(domain, [care_context_reference],
                                                          case_types=case_types_for_resource_types)


def medication_request_cases_from_condition(domain, condition_cases, medication_request_case_type):
    return CommCareCase.objects.get_reverse_indexed_cases(domain, [case.case_id for case in condition_cases],
                                                          medication_request_case_type)


def _get_resource_type_case(case, fhir_setup):
    return next(resource_type.name for resource_type in fhir_setup if resource_type.case_type.name == case.type)


def cases_as_fhir_entries(cases, fhir_resource_types):
    entries = {}
    for case in cases:
        try:
            data = build_fhir_resource(case)
            resource = _get_resource_type_case(case, fhir_resource_types)
            if resource in entries:
                entries[resource].append(data)
            else:
                entries[resource] = [data]
        except ConfigurationError:
            raise Exception('FHIR configuration error. Please notify administrator')
    return entries


def generate_reference_from_resource(resource):
    return {
        'type': resource['resourceType'],
        'reference': f"{resource['resourceType']}/{resource['id']}"
    }


def create_composition(entries, hi_type):
    # TODO Check for id
    composition = {
        'resourceType': 'Composition',
        'title': hi_type.TEXT,
        'id': "1"
    }

    subject = entries[hi_type.SUBJECT_RESOURCE][0]
    composition['subject'] = generate_reference_from_resource(subject)

    composition['status'] = 'final'
    composition['date'] = datetime.now(timezone.utc).isoformat()
    composition['type'] = {
        'coding': hi_type.CODING,
        'text': hi_type.TEXT
    }
    # First resource type from the list that is configured is considered here as author
    author_resource_type = next(resource for resource in hi_type.AUTHOR_RESOURCE_CHOICES if resource in entries.keys())
    author = entries[author_resource_type][0]
    composition['author'] = [generate_reference_from_resource(author)]

    if 'Encounter' in entries.keys():
        composition['encounter'] = generate_reference_from_resource(entries['Encounter'][0])

    composition['section'] = [{
        'title': hi_type.TEXT,
        'code': {
            'coding': hi_type.CODING
        },
        'entry': []
    }]
    for entry, resources in entries.items():
        if entry in hi_type.SECTION_ENTRY_RESOURCE_CHOICES:
            for resource in resources:
                composition['section'][0]['entry'].append(generate_reference_from_resource(resource))
    return composition


def generate_document_bundle(domain, entries, composition, care_context_reference):
    bundle = {
        'resourceType': 'Bundle',
        'type': 'document',
        'timestamp': composition['date'],
        'meta': {
            'versionId': "1"
        },
        # TODO Add valid values below
        'identifier': {
            "system": "https://india.commcare.org",
            "value": care_context_reference
        },
        'entry': []
    }
    # TODO Check if Full URL should be absolute
    bundle['entry'].append({
        'resource': composition,
        'fullUrl': f"{composition['resourceType']}/{composition['id']}"
    })
    for entry, resources in entries.items():
        for resource in resources:
            bundle['entry'].append({
                'resource': resource,
                'fullUrl': f"{entry}/{resource['id']}"
            })
    return bundle


def get_medication_request_cases(domain, cases, fhir_resource_types):
    # Medication Request Case type is linked to Condition for Prescription
    medication_request_cases = []
    medication_request_case_type = next(resource_type.case_type.name for resource_type in fhir_resource_types
                                        if resource_type.name == 'MedicationRequest')
    if medication_request_case_type:
        condition_case_type = next(resource_type.case_type.name for resource_type in fhir_resource_types
                                   if resource_type.name == 'Condition')
        if condition_case_type:
            condition_cases = [case for case in cases if case.type == condition_case_type]
            medication_request_cases.extend(medication_request_cases_from_condition(domain, condition_cases,
                                                                           [medication_request_case_type]))
    return medication_request_cases


# TODO Consider modifying below class and using it
class ABDMDocumentBundleGenerator:

    def __init__(self, domain, care_context_reference, health_information_type):
        self.domain = domain
        self.care_context_reference = care_context_reference
        self.health_information_type = health_information_type
        self.clinical_artifact = artifact_from_health_information_type(health_information_type)
        self.fhir_resource_types = fhir_resources_configured_for_domain(domain)
        self.resource_to_case_type = self.get_resource_to_case_type()

    def get_resource_to_case_type(self):
        resource_to_case_type = {}
        for resource_type in self.fhir_resource_types:
            resource_to_case_type[resource_type.name] = resource_type.case_type.name
        return resource_to_case_type

    def validate_config(self):
        validate_fhir_resources_config(self.clinical_artifact, self.resource_to_case_type.keys())

    def generate(self):
        cases = fetch_related_cases(self.domain, self.care_context_reference, self.resource_to_case_type.values())
        if self.clinical_artifact.HI_TYPE == PrescriptionRecord:
            cases.extend(get_medication_request_cases(self.domain, cases, self.fhir_resource_types))

        fhir_entries = cases_as_fhir_entries(cases, self.fhir_resource_types)
        composition = create_composition(fhir_entries, self.clinical_artifact)
        return generate_document_bundle(fhir_entries, composition, self.care_context_reference)


def document_bundle_from_hq(care_context_reference, health_information_type):
    # TODO Get domain from care_context_reference if possible
    domain = 'abdm-eimnci'
    clinical_artifact = artifact_from_health_information_type(health_information_type)

    fhir_resource_types = fhir_resources_configured_for_domain(domain)
    resource_configured = [resource_type.name for resource_type in fhir_resource_types]
    case_type_for_resources = [resource_type.case_type.name for resource_type in fhir_resource_types]

    validate_fhir_resources_config(clinical_artifact, resource_configured)

    cases = fetch_related_cases(domain, care_context_reference, case_type_for_resources)
    if clinical_artifact.HI_TYPE == HealthInformationType.PRESCRIPTION:
        cases.extend(get_medication_request_cases(domain, cases, fhir_resource_types))

    fhir_entries = cases_as_fhir_entries(cases, fhir_resource_types)
    composition = create_composition(fhir_entries, clinical_artifact)
    return generate_document_bundle(domain, fhir_entries, composition, care_context_reference)
