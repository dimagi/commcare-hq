from typing import List, Tuple

from django.conf import settings
from django.contrib.sites.models import Site

from requests import Response

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.motech.requests import Requests
from corehq.motech.value_source import CaseTriggerInfo

from .const import FHIR_BUNDLE_TYPES, FHIR_VERSIONS, XMLNS_FHIR
from .models import build_fhir_resource_for_info


def register_patients(
    requests: Requests,
    info_resources_list: List[tuple],
):
    for info, resources in info_resources_list:
        if info.extra_fields['external_id']:
            continue  # Case is already registered
        for resource in resources:
            if resource['resourceType'] != 'Patient':
                continue
            response = requests.post('Patient/', json=resource,
                                     raise_for_status=True)
            set_external_id(info, response.json()['id'])
            resources.remove(response)
            # TODO: Update other resources to refer to the new Patient


def get_info_resources_list(
    case_trigger_infos: List[CaseTriggerInfo],
    fhir_version: str,
) -> List[Tuple[CaseTriggerInfo, dict]]:
    """
    Returns pairs of CaseTriggerInfo + the FHIR resource they map to.
    """
    results = []
    for info in case_trigger_infos:
        resource = build_fhir_resource_for_info(info, fhir_version)
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
        raise ValueError(f'Unknown FHIR Bundle type {bundle_type!r}')
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


def set_external_id(info, external_id):
    info.extra_fields['external_id'] = external_id
    case_block = CaseBlock(
        case_id=info.case_id,
        external_id=external_id,
        create=False,
    )
    submit_case_blocks(
        [case_block.as_text()],
        info.domain,
        xmlns=XMLNS_FHIR,
    )
