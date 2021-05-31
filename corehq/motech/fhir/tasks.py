from typing import Generator
from uuid import uuid4

from celery.schedules import crontab
from celery.task import periodic_task

from corehq import toggles
from corehq.motech.requests import Requests

from .bundle import get_bundle, iter_bundle, get_next_url
from .const import IMPORT_FREQUENCY_DAILY, SYSTEM_URI_CASE_ID
from .models import FHIRImporter, FHIRImporterResourceType


@periodic_task(run_every=crontab(hour=5, minute=5), queue='background_queue')
def run_daily_importers():
    for importer in (
        FHIRImporter.objects.filter(
            frequency=IMPORT_FREQUENCY_DAILY
        ).select_related('connection_settings').all()
    ):
        run_importer(importer)


def run_importer(importer):
    """
    Poll remote API and import resources as CommCare cases.

    ServiceRequest resources are treated specially for workflows that
    handle referrals across systems like CommCare.
    """
    if not toggles.FHIR_INTEGRATION.enabled(importer.domain):
        return
    requests = importer.connection_settings.get_requests()
    # TODO: Check service is online, else retry with exponential backoff
    for resource_type in (
            importer.resource_types
            .filter(import_related_only=False)
            .prefetch_related('jsonpaths_to_related_resource_types')
            .all()
    ):
        import_resource_type(requests, resource_type)


def import_resource_type(
    requests: Requests,
    resource_type: FHIRImporterResourceType,
):
    try:
        for resource in iter_resources(requests, resource_type):
            import_resource(requests, resource_type, resource)
    except Exception as err:
        requests.notify_exception(str(err))


def iter_resources(
    requests: Requests,
    resource_type: FHIRImporterResourceType,
) -> Generator:
    searchset_bundle = get_bundle(
        requests,
        endpoint=f"{resource_type.name}/",
        params=resource_type.search_params,
    )
    while True:
        yield from iter_bundle(searchset_bundle)
        url = get_next_url(searchset_bundle)
        if url:
            searchset_bundle = get_bundle(requests, url=url)
        else:
            break


def import_resource(
    requests: Requests,
    resource_type: FHIRImporterResourceType,
    resource: dict,
):
    if resource_type.name == 'ServiceRequest':
        try:
            case_id = claim_service_request(requests, resource)
        except ServiceRequestNotActive:
            return  # Nothing to do
    # TODO:
    #   * Map resource properties to case properties
    #   * Save case
    #   * Don't forget to recurse related resources
    pass


def claim_service_request(requests, service_request):
    """
    Uses `ETag`_ to prevent a race condition.

    .. _ETag: https://www.hl7.org/fhir/http.html#concurrency
    """
    endpoint = f"ServiceRequest/{service_request['id']}"
    response = requests.get(endpoint, raise_for_status=True)
    etag = response.headers['ETag']
    service_request = response.json()
    if service_request['status'] != 'active':
        raise ServiceRequestNotActive

    case_id = uuid4().hex
    service_request['status'] = 'on-hold'
    service_request.setdefault('identifier', [])
    service_request['identifier'].append({
        'system': SYSTEM_URI_CASE_ID,
        'value': case_id,
    })
    headers = {'If-Match': etag}
    response = requests.put(endpoint, json=service_request, headers=headers)
    if 200 <= response.status < 300:
        return case_id
    if response.status == 412:
        # ETag didn't match. Try again.
        return claim_service_request(requests, service_request)
    else:
        response.raise_for_status()


class ServiceRequestNotActive(Exception):
    pass
