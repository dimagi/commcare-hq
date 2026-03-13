from django.db.models import Max
from django.http import Http404

from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
)


def create_endpoint(domain, name, target_type, target_name, parameters, query):
    """Create a new endpoint with its first version."""
    endpoint = CaseSearchEndpoint.objects.create(
        domain=domain,
        name=name,
        target_type=target_type,
        target_name=target_name,
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


def save_new_version(endpoint, parameters, query):
    """Create a new version for an existing endpoint."""
    max_version = endpoint.versions.aggregate(
        max_v=Max('version_number')
    )['max_v'] or 0
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
    """Return a single endpoint, raising Http404 if not found or wrong domain."""
    try:
        return CaseSearchEndpoint.objects.select_related(
            'current_version'
        ).get(
            pk=endpoint_id,
            domain=domain,
            is_active=True,
        )
    except CaseSearchEndpoint.DoesNotExist:
        raise Http404


def get_version(endpoint, version_number):
    """Return a specific version, raising Http404 if not found."""
    try:
        return endpoint.versions.get(version_number=version_number)
    except CaseSearchEndpointVersion.DoesNotExist:
        raise Http404


def deactivate_endpoint(endpoint):
    """Soft-delete an endpoint."""
    endpoint.is_active = False
    endpoint.save(update_fields=['is_active'])
