from typing import List, Tuple

from requests import HTTPError, Response

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.motech.repeater_helpers import RepeaterResponse
from corehq.motech.requests import Requests, json_or_http_error
from corehq.motech.value_source import CaseTriggerInfo

from .const import FHIR_BUNDLE_TYPES, FHIR_VERSIONS, XMLNS_FHIR
from .matchers import PatientMatcher
from .models import build_fhir_resource_for_info
from .searchers import PatientSearcher
from .utils import resource_url


def register_patients(
    requests: Requests,
    info_resource_list: List[tuple],
    registration_enabled: bool,
    search_enabled: bool,
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
        if search_enabled:
            patient = find_patient(requests, resource)  # Raises DuplicateWarning
        else:
            patient = None
        if patient:
            _set_external_id(info, patient['id'], repeater_id)
            info_resource_list_to_send.append((info, resource))
        elif registration_enabled:
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
            _check_id(match)
            return match
    return None


def register_patient(requests, resource):
    response = requests.post('Patient/', json=resource, raise_for_status=True)
    patient = json_or_http_error(response)
    _check_id(patient)
    return patient


def _check_id(patient):
    if 'id' not in patient:
        response = RepeaterResponse(status_code=500, reason='Bad response')
        raise HTTPError(
            'Remote service returned a patient missing an "id" property',
            response=response,
        )


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
    repeater_id: str,
) -> Response:
    if not info_resources_list:
        # Either the payload had no data to be forwarded, or resources
        # were all patients to be registered: Nothing left to send.
        return RepeaterResponse(204, "No content")

    if len(info_resources_list) == 1:
        info, resource = info_resources_list[0]
        return send_resource(requests, info, resource, repeater_id)

    return send_bundle(requests, info_resources_list, fhir_version)


def send_resource(
    requests: Requests,
    info: CaseTriggerInfo,
    resource: dict,
    repeater_id: str,
    *,
    raise_on_ext_id: bool = False,
) -> Response:
    external_id = info.extra_fields['external_id']
    if external_id:
        endpoint = f"{resource['resourceType']}/{external_id}"
        response = requests.put(endpoint, json=resource, raise_for_status=True)
        return response

    endpoint = f"{resource['resourceType']}/"
    response = requests.post(endpoint, json=resource, raise_for_status=True)
    try:
        _set_external_id(info, response.json()['id'], repeater_id)
    except (ValueError, KeyError) as err:
        # The remote service returned a 2xx response, but did not
        # return JSON, or the JSON does not include an ID.
        if raise_on_ext_id:
            msg = 'Unable to parse response from remote FHIR service'
            raise HTTPError(msg, response=response) from err
    return response


def send_bundle(
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
    fhir_version_name = dict(FHIR_VERSIONS)[fhir_version]
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
        url = resource_url(
            info.domain,
            fhir_version_name,
            resource['resourceType'],
            resource['id'],
        )
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
