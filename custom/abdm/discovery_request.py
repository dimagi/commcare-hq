from datetime import date

from abdm_integrator.const import IdentifierType
from abdm_integrator.hip.exceptions import (
    DiscoveryMultiplePatientsFoundError,
    DiscoveryNoPatientFoundError,
)

from corehq.apps.es import queries
from corehq.apps.es.case_search import (
    CaseSearchES,
    case_property_range_query,
    sounds_like_text_query,
)
from corehq.form_processor.models import CommCareCase
from corehq.toggles import ABDM_INTEGRATION
from corehq.toggles.shortcuts import find_domains_with_toggle_enabled

PATIENT_CASE_TYPE = 'abdm_patient_discovery_data'
HIP_ID_PROPERTY = 'hip_id'
HEALTH_ID_PROPERTY = 'abha_address'
PHONE_NUMBER_PROPERTY = 'phone_number'
DATE_OF_BIRTH_PROPERTY = 'dob'
GENDER_PROPERTY = 'sex'
ABHA_NUMBER_PROPERTY = 'abha_id'
NAME_PROPERTY = 'case_name'

CARE_CONTEXT_CASE_TYPE = 'fhir_care_context'
YEARS_RANGE_TO_MATCH = 2


def base_discover_query(domains, hip_id):
    return CaseSearchES().domain(domains).case_type(PATIENT_CASE_TYPE).case_property_query(
        HIP_ID_PROPERTY,
        hip_id
    ).sort('opened_on')


def get_patient_by_health_id(patient_details, hip_id, abdm_enabled_domains):
    health_id_query = base_discover_query(abdm_enabled_domains, hip_id).case_property_query(
        HEALTH_ID_PROPERTY,
        patient_details.health_id
    )
    return health_id_query.values('name', 'domain', 'indices.referenced_id')


def get_patient_by_demographics(patient_details, hip_id, abdm_enabled_domains):
    demographics_query = base_discover_query(abdm_enabled_domains, hip_id).case_property_query(
        PHONE_NUMBER_PROPERTY, patient_details.mobile
    ).case_property_query(GENDER_PROPERTY, patient_details.gender)
    start_date = date(patient_details.year_of_birth - YEARS_RANGE_TO_MATCH, 1, 1)
    end_date = date(patient_details.year_of_birth + YEARS_RANGE_TO_MATCH, 12, 31)
    demographics_query.add_query(
        case_property_range_query(DATE_OF_BIRTH_PROPERTY, gte=start_date, lte=end_date),
        clause=queries.MUST
    )
    demographics_query.add_query(
        sounds_like_text_query(NAME_PROPERTY, patient_details.name),
        clause=queries.MUST
    )
    return demographics_query.values('name', 'domain', 'indices.referenced_id', 'case_properties')


def get_patient(patient_details, hip_id):
    abdm_enabled_domains = find_domains_with_toggle_enabled(ABDM_INTEGRATION)
    results = get_patient_by_health_id(patient_details, hip_id, abdm_enabled_domains)
    if results:
        return results, IdentifierType.HEALTH_ID
    results = get_patient_by_demographics(patient_details, hip_id, abdm_enabled_domains)
    return results, IdentifierType.MOBILE


def get_care_context_cases(discovered_patients):
    care_context_cases = []
    for record in discovered_patients:
        care_context_cases.extend(
            CommCareCase.objects.get_reverse_indexed_cases(
                record['domain'],
                [record['indices']['referenced_id']],
                case_types=[CARE_CONTEXT_CASE_TYPE]
            )
        )
    return care_context_cases


def care_context_details_from_cases(care_context_cases):
    care_context_details = []
    for case in care_context_cases:
        data = {
            'referenceNumber': case.case_id,
            'display': case.name,
            'hiTypes': case.case_json['all_hi_types'].split(','),
            'additionalInfo': {
                'domain': case.domain,
                'record_date': case.closed_on.isoformat()
            }
        }
        care_context_details.append(data)
    return care_context_details


def case_property_value_by_key(case_properties, key):
    return next((case_property['value'] for case_property in case_properties if case_property['key'] == key), None)


def _get_data_to_match(patient_record):
    return (
        patient_record['name'],
        case_property_value_by_key(patient_record['case_properties'], DATE_OF_BIRTH_PROPERTY)
    )


def check_if_discovered_patients_are_same(patient_records):
    first_patient_data_to_match = _get_data_to_match(patient_records[0])
    for record in patient_records[1:]:
        if _get_data_to_match(record) != first_patient_data_to_match:
            return False
    return True


def discover_patient_with_care_contexts(patient_details, hip_id):
    discovered_patients, matched_by = get_patient(patient_details, hip_id)
    if not discovered_patients:
        raise DiscoveryNoPatientFoundError()
    # In case multiple discoveries via demographics, they are considered as same
    # patient only if their Date of birth and name matches
    if matched_by == IdentifierType.MOBILE and len(discovered_patients) > 1:
        if not check_if_discovered_patients_are_same(discovered_patients):
            raise DiscoveryMultiplePatientsFoundError()
    # In case of same patient discovered across multiple hip ids,
    # consider first registered patient case id as the reference number
    discovery_result = {
        'referenceNumber': discovered_patients[0]['indices']['referenced_id'],
        'display': discovered_patients[0]['name'],
        'careContexts': [],
        'matchedBy': [
            matched_by
        ]
    }
    care_context_cases = get_care_context_cases(discovered_patients)
    discovery_result['careContexts'] = care_context_details_from_cases(care_context_cases)
    return discovery_result
