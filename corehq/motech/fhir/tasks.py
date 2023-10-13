from collections import namedtuple
from typing import Generator, List
from uuid import uuid4

from django.conf import settings

from celery.schedules import crontab
from jsonpath_ng.ext.parser import parse as jsonpath_parse

from casexml.apps.case.mock import CaseBlock

from corehq import toggles
from corehq.apps.celery import periodic_task, task
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase
from corehq.motech.const import (
    IMPORT_FREQUENCY_DAILY,
    IMPORT_FREQUENCY_MONTHLY,
    IMPORT_FREQUENCY_WEEKLY,
)
from corehq.motech.exceptions import ConfigurationError, RemoteAPIError
from corehq.motech.requests import Requests
from corehq.motech.utils import simplify_list

from .bundle import get_bundle, get_next_url, iter_bundle
from .const import SYSTEM_URI_CASE_ID, XMLNS_FHIR
from .models import FHIRImportConfig, FHIRImportResourceType

ParentInfo = namedtuple(
    'ParentInfo',
    ['child_case_id', 'parent_ref', 'parent_resource_type'],
)


@periodic_task(
    run_every=crontab(hour=5, minute=5),
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def run_daily_importers():
    for importer_id in (
            FHIRImportConfig.objects
            .filter(frequency=IMPORT_FREQUENCY_DAILY)
            .values_list('id', flat=True)
    ):
        run_importer.delay(importer_id)


@periodic_task(
    run_every=crontab(hour=5, minute=5, day_of_week=6),  # Saturday
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def run_weekly_importers():
    for importer_id in (
            FHIRImportConfig.objects
            .filter(frequency=IMPORT_FREQUENCY_WEEKLY)
            .values_list('id', flat=True)
    ):
        run_importer.delay(importer_id)


@periodic_task(
    run_every=crontab(hour=5, minute=5, day_of_month=1),
    queue=settings.CELERY_PERIODIC_QUEUE,
)
def run_monthly_importers():
    for importer_id in (
            FHIRImportConfig.objects
            .filter(frequency=IMPORT_FREQUENCY_MONTHLY)
            .values_list('id', flat=True)
    ):
        run_importer.delay(importer_id)


@task(queue='background_queue', ignore_result=True)
def run_importer(importer_id):
    """
    Poll remote API and import resources as CommCare cases.

    ServiceRequest resources are treated specially for workflows that
    handle referrals across systems like CommCare.
    """
    importer = (
        FHIRImportConfig.objects
        .select_related('connection_settings')
        .get(pk=importer_id)
    )
    if not toggles.FHIR_INTEGRATION.enabled(importer.domain):
        return
    requests = importer.connection_settings.get_requests()
    # TODO: Check service is online, else retry with exponential backoff
    child_cases = []
    for resource_type in (
            importer.resource_types
            .filter(import_related_only=False)
            .prefetch_related('jsonpaths_to_related_resource_types')
            .all()
    ):
        import_resource_type(requests, resource_type, child_cases)
    create_parent_indices(importer, child_cases)


def import_resource_type(
    requests: Requests,
    resource_type: FHIRImportResourceType,
    child_cases: List[ParentInfo],
):
    try:
        for resource in iter_resources(requests, resource_type):
            import_resource(requests, resource_type, resource, child_cases)
    except Exception as err:
        requests.notify_exception(str(err))


def iter_resources(
    requests: Requests,
    resource_type: FHIRImportResourceType,
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
    resource_type: FHIRImportResourceType,
    resource: dict,
    child_cases: List[ParentInfo],
):
    if 'resourceType' not in resource:
        raise RemoteAPIError(
            "FHIR resource missing required property 'resourceType'"
        )
    if resource['resourceType'] != resource_type.name:
        raise RemoteAPIError(
            f"API request for resource type {resource_type.name!r} returned "
            f"resource type {resource['resourceType']!r}."
        )

    case_id = str(uuid4())
    if resource_type.name == 'ServiceRequest':
        try:
            resource = claim_service_request(requests, resource, case_id)
        except ServiceRequestNotActive:
            # ServiceRequests whose status is "active" are available for
            # CommCare to claim. If this ServiceRequest is no longer
            # active, then it is not available any more, and CommCare
            # should not import it.
            return

    case_block = build_case_block(resource_type, resource, case_id)
    submit_case_blocks(
        [case_block.as_text()],
        resource_type.domain,
        xmlns=XMLNS_FHIR,
        device_id=f'FHIRImportConfig-{resource_type.import_config.pk}',
    )
    import_related(
        requests,
        resource_type,
        resource,
        case_block.case_id,
        child_cases,
    )


def claim_service_request(requests, service_request, case_id, attempt=0):
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

    service_request['status'] = 'on-hold'
    service_request.setdefault('identifier', [])
    has_case_id = any(id_.get('system') == SYSTEM_URI_CASE_ID
                      for id_ in service_request['identifier'])
    if not has_case_id:
        service_request['identifier'].append({
            'system': SYSTEM_URI_CASE_ID,
            'value': case_id,
        })
    headers = {'If-Match': etag}
    response = requests.put(endpoint, json=service_request, headers=headers)
    if 200 <= response.status_code < 300:
        return service_request
    if response.status_code == 412 and attempt < 3:
        # ETag didn't match. Try again.
        return claim_service_request(requests, service_request, case_id, attempt + 1)
    else:
        response.raise_for_status()


def build_case_block(resource_type, resource, suggested_case_id):
    """
    Returns a `CaseBlock` to create or update a case corresponding to a
    FHIR resource.

    :param resource_type: A FHIRResourceType
    :param resource: A dict
    :param suggested_case_id: Used if `resource` doesn't correspond to a
        case already.
    :return: A CaseBlock
    """
    domain = resource_type.domain
    case_type = resource_type.case_type.name
    owner_id = resource_type.import_config.owner_id
    case = None

    caseblock_kwargs = get_caseblock_kwargs(resource_type, resource)
    if 'id' in resource:
        external_id = resource['id']
        caseblock_kwargs['external_id'] = external_id
    else:
        external_id = None
    case_id = get_case_id_or_none(resource)
    if case_id:
        case = get_case_by_id(domain, case_id)
        # If we have a case_id we can be pretty sure we can get a case
        # ... unless it's been deleted. If so, fall back on external_id.
    if case is None and external_id:
        case = get_case_by_external_id(domain, external_id, case_type)

    return CaseBlock(
        create=case is None,
        case_id=case.case_id if case else suggested_case_id,
        owner_id=owner_id,
        case_type=case_type,
        **caseblock_kwargs,
    )


def get_case_id_or_none(resource):
    """
    If ``resource`` has a CommCare case ID identifier, return its value,
    otherwise return None.
    """
    if 'identifier' in resource:
        case_id_identifier = [id_ for id_ in resource['identifier']
                              if id_.get('system') == SYSTEM_URI_CASE_ID]
        if case_id_identifier:
            return case_id_identifier[0]['value']
    return None


def get_case_by_id(domain, case_id):
    try:
        case = CommCareCase.objects.get_case(case_id, domain)
    except (CaseNotFound, KeyError):
        return None
    return case if case.domain == domain and not case.is_deleted else None


def get_case_by_external_id(domain, external_id, case_type):
    try:
        case = CommCareCase.objects.get_case_by_external_id(
            domain, external_id, case_type, raise_multiple=True)
    except CommCareCase.MultipleObjectsReturned:
        return None
    return case if case is not None and not case.is_deleted else None


def get_caseblock_kwargs(resource_type, resource):
    name_properties = {"name", "case_name"}
    kwargs = {
        'case_name': get_name(resource),
        'update': {}
    }
    for value_source in resource_type.iter_case_property_value_sources():
        value = value_source.get_import_value(resource)
        if value is not None:
            if value_source.case_property in name_properties:
                kwargs['case_name'] = value
            else:
                kwargs['update'][value_source.case_property] = value
    return kwargs


def get_name(resource):
    """
    Returns a name, or a code, or an empty string.
    """
    if resource.get('name'):
        return resource['name'][0].get('text', '')
    if resource.get('code'):
        return resource['code'][0].get('text', '')
    return ''


def import_related(
    requests: Requests,
    resource_type: FHIRImportResourceType,
    resource: dict,
    case_id: str,
    child_cases: List[ParentInfo],
):
    for rel in resource_type.jsonpaths_to_related_resource_types.all():
        jsonpath = jsonpath_parse(rel.jsonpath)
        reference = simplify_list([x.value for x in jsonpath.find(resource)])
        validate_parent_ref(reference, rel.related_resource_type)
        related_resource = get_resource(requests, reference)

        if rel.related_resource_is_parent:
            parent_info = ParentInfo(
                child_case_id=case_id,
                parent_ref=reference,
                parent_resource_type=rel.related_resource_type,
            )
            child_cases.append(parent_info)

        import_resource(
            requests,
            rel.related_resource_type,
            related_resource,
            child_cases,
        )


def validate_parent_ref(parent_ref, parent_resource_type):
    """
    Validates that ``parent_ref`` is a relative reference with an
    expected resource type. e.g. "Patient/12345"
    """
    try:
        resource_type_name, resource_id = parent_ref.split('/')
    except (AttributeError, ValueError):
        raise ConfigurationError(
            f'Unexpected reference format {parent_ref!r}')
    if resource_type_name != parent_resource_type.name:
        raise ConfigurationError(
            'Resource type does not match expected parent resource type')


def get_resource(requests, reference):
    """
    Fetches a resource.

    ``reference`` must be a relative reference. e.g. "Patient/12345"
    """
    response = requests.get(endpoint=reference, raise_for_status=True)
    return response.json()


def create_parent_indices(
    importer: FHIRImportConfig,
    child_cases: List[ParentInfo],
):
    """
    Creates parent-child relationships on imported cases.

    If ``ResourceTypeRelationship.related_resource_is_parent`` is
    ``True`` then this function will add an ``index`` on the child case
    to its parent case.
    """
    if not child_cases:
        return

    case_blocks = []
    for child_case_id, parent_ref, parent_resource_type in child_cases:
        resource_type_name, external_id = parent_ref.split('/')
        parent_case = get_case_by_external_id(
            parent_resource_type.domain,
            external_id,
            parent_resource_type.case_type.name,
        )
        if not parent_case:
            raise ConfigurationError(
                f'Case not found with external_id {external_id!r}')

        case_blocks.append(CaseBlock(
            child_case_id,
            index={'parent': (parent_case.type, parent_case.case_id)},
        ))
    submit_case_blocks(
        [cb.as_text() for cb in case_blocks],
        importer.domain,
        xmlns=XMLNS_FHIR,
        device_id=f'FHIRImportConfig-{importer.pk}',
    )


class ServiceRequestNotActive(Exception):
    pass
