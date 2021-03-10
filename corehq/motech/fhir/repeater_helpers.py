from typing import List, Tuple

from django.conf import settings
from django.contrib.sites.models import Site

from requests import Response

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.motech.requests import Requests
from corehq.motech.value_source import CaseTriggerInfo

from .const import FHIR_BUNDLE_TYPES, FHIR_VERSIONS, XMLNS_FHIR
from .matchers import PatientMatcher
from .models import build_fhir_resource_for_info
from .searchers import PatientSearcher


def register_patients(
    requests: Requests,
    info_resource_list: List[tuple],
    repeater_id: str,
) -> List[tuple]:

    info_resource_list_to_send = []
    for info, resource in info_resource_list:
        if resource['resourceType'] != 'Patient':
            info_resource_list_to_send.append((info, resource))
            continue
        if info.extra_fields['external_id']:
            # Patient is already registered
            info_resource_list_to_send.append((info, resource))
            continue
        patient = find_patient(requests, resource)  # Raises DuplicateWarning
        if patient:
            _set_external_id(info, patient['id'], repeater_id)
            info_resource_list_to_send.append((info, resource))
        else:
            patient = register_patient(requests, resource)
            _set_external_id(info, patient['id'], repeater_id)
            # Don't append `resource` to `info_resource_list_to_send`
            # because the remote service has all its data now.
    return info_resource_list_to_send


def find_patient(requests, resource):
    searcher = PatientSearcher(requests, resource)
    matcher = PatientMatcher(resource)
    for search in searcher.iter_searches():
        candidates = search.iter_candidates()
        match = matcher.find_match(candidates)  # Raises DuplicateWarning
        if match:
            return match
    return None


def register_patient(requests, resource):
    response = requests.post('Patient/', json=resource, raise_for_status=True)
    return response.json()


def get_info_resource_list(
    case_trigger_infos: List[CaseTriggerInfo],
    resource_types_by_case_type: dict,
) -> List[Tuple[CaseTriggerInfo, dict]]:
    """
    Returns pairs of CaseTriggerInfo + the FHIR resource they map to.
    """
    results = []
    for info in case_trigger_infos:
        resource_type = resource_types_by_case_type[info.type]
        resource = build_fhir_resource_for_info(info, resource_type)
        if resource:
            # We return `info` with `resource` because
            # `get_bundle_entries()` will need both.
            results.append((info, resource))
    return results


def send_resources(
    requests: Requests,
    info_resources_list: List[tuple],
    fhir_version: str,
) -> Response:
    entries = get_bundle_entries(info_resources_list, fhir_version)
    bundle = create_bundle(entries, bundle_type='transaction')
    response = requests.post('/', json=bundle)
    return response


def get_bundle_entries(
    info_resources_list: List[tuple],
    fhir_version: str,
) -> List[dict]:
    entries = []
    for info, resource in info_resources_list:
        external_id = info.extra_fields['external_id']
        if external_id:
            request = {
                'method': 'PUT',
                'url': f"{resource['resourceType']}/{external_id}",
            }
        else:
            request = {
                'method': 'POST',
                'url': f"{resource['resourceType']}/",
            }
        url = get_full_url(info.domain, resource, fhir_version)
        entries.append({
            'fullUrl': url,
            'resource': resource,
            'request': request,
        })
    return entries


def create_bundle(
    entries: List[dict],
    bundle_type: str,
) -> dict:
    if bundle_type not in FHIR_BUNDLE_TYPES:
        valid_values = ', '.join([repr(b) for b in FHIR_BUNDLE_TYPES])
        raise ValueError(f'Unknown FHIR Bundle type {bundle_type!r}. '
                         f'Valid values are: {valid_values}')
    return {
        'type': bundle_type,
        'entry': entries,
        'resourceType': 'Bundle',
    }


def get_full_url(
    domain: str,
    resource: dict,
    fhir_version: str,
) -> str:
    # TODO: Use `absolute_reverse` as soon as we have an API view
    proto = 'http' if settings.DEBUG else 'https'
    host = Site.objects.get_current().domain
    ver = dict(FHIR_VERSIONS)[fhir_version].lower()
    return (f'{proto}://{host}/a/{domain}/api'
            f"/fhir/{ver}/{resource['resourceType']}/{resource['id']}")


def _set_external_id(info, external_id, repeater_id):
    """
    Set "external_id" property on the case represented by ``info``.
    """
    case_block = CaseBlock(
        case_id=info.case_id,
        external_id=external_id,
        create=False,
    )
    submit_case_blocks(
        [case_block.as_text()],
        info.domain,
        xmlns=XMLNS_FHIR,
        device_id=f'FHIRRepeater-{repeater_id}',
    )
    # If case was matched, set external_id to update remote resource
    info.extra_fields['external_id'] = external_id
