from django.db import IntegrityError, transaction
from django.db.models import Max

from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
)


class FilterSpecValidationError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(f'Validation errors: {errors}')


class EndpointNotFound(Exception):
    pass


@transaction.atomic
def create_endpoint(domain, name, target_type, target_name, parameters, query):
    """Create a new endpoint with its first version."""
    errors = []
    if errors:
        raise FilterSpecValidationError(errors)
    try:
        with transaction.atomic():
            endpoint = CaseSearchEndpoint.objects.create(
                domain=domain,
                name=name,
                target_type=target_type,
                target_name=target_name,
            )
    except IntegrityError:
        raise FilterSpecValidationError(
            [f"An endpoint named '{name}' already exists in this project."]
        )
    version = CaseSearchEndpointVersion.objects.create(
        endpoint=endpoint,
        version_number=1,
        parameters=parameters,
        query=query,
    )
    endpoint.current_version = version
    endpoint.save(update_fields=['current_version'])
    return endpoint


@transaction.atomic
def save_new_version(endpoint, parameters, query):
    """Create a new version for an existing endpoint."""
    errors = []
    if errors:
        raise FilterSpecValidationError(errors)
    # Acquire a row lock so concurrent save_new_version calls are serialized.
    # The lock is held for the duration of the transaction.
    locked_endpoint = CaseSearchEndpoint.objects.select_for_update().get(pk=endpoint.pk)
    max_version = (
        locked_endpoint.versions.aggregate(max_v=Max('version_number'))['max_v'] or 0
    )
    version = CaseSearchEndpointVersion.objects.create(
        endpoint=endpoint,
        version_number=max_version + 1,
        parameters=parameters,
        query=query,
    )
    endpoint.current_version = version
    endpoint.save(update_fields=['current_version'])
    return version

def list_endpoints(domain):
    """Return active endpoints for a domain."""
    return CaseSearchEndpoint.objects.filter(
        domain=domain,
        is_active=True,
    ).select_related('current_version')


def get_endpoint(domain, endpoint_id):
    """Return a single endpoint, raising EndpointNotFound if not found or wrong domain."""
    try:
        return CaseSearchEndpoint.objects.select_related(
            'current_version'
        ).get(
            pk=endpoint_id,
            domain=domain,
            is_active=True,
        )
    except CaseSearchEndpoint.DoesNotExist:
        raise EndpointNotFound(endpoint_id)


def get_version(endpoint, version_number):
    """Return a specific version, raising EndpointNotFound if not found."""
    try:
        return endpoint.versions.get(version_number=version_number)
    except CaseSearchEndpointVersion.DoesNotExist:
        raise EndpointNotFound(version_number)


def deactivate_endpoint(endpoint):
    """Soft-delete an endpoint."""
    endpoint.is_active = False
    endpoint.save(update_fields=['is_active'])
