from typing import List, Tuple

from django.conf import settings
from django.contrib.sites.models import Site
from requests import Response

from corehq.motech.requests import Requests
from corehq.motech.value_source import CaseTriggerInfo

from .const import FHIR_BUNDLE_TYPES, FHIR_VERSIONS
from .models import build_fhir_resource_for_info


def register_patients(
    requests: Requests,
    info_resources_list: List[tuple],
):
    raise NotImplementedError


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
