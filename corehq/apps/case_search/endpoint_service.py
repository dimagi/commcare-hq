from django.db.models import Max

from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
)


def create_endpoint(domain, name, target_type, target_name, parameters, query):
    endpoint = CaseSearchEndpoint.objects.create(
        domain=domain,
        name=name,
        target_type=target_type,
        target_name=target_name,
    )
    version = _create_version(endpoint, parameters, query)
    endpoint.current_version = version
    endpoint.save(update_fields=['current_version'])
    return endpoint


def save_new_version(endpoint, parameters, query):
    version = _create_version(endpoint, parameters, query)
    endpoint.current_version = version
    endpoint.save(update_fields=['current_version'])
    return version


def list_endpoints(domain):
    return CaseSearchEndpoint.objects.filter(
        domain=domain, is_active=True,
    ).select_related('current_version')


def get_endpoint(domain, endpoint_id):
    return CaseSearchEndpoint.objects.get(
        domain=domain, id=endpoint_id, is_active=True,
    )


def get_version(endpoint, version_number):
    return endpoint.versions.get(version_number=version_number)


def deactivate_endpoint(endpoint):
    endpoint.is_active = False
    endpoint.save(update_fields=['is_active'])


def _create_version(endpoint, parameters, query):
    last = endpoint.versions.aggregate(
        max_v=Max('version_number'),
    )['max_v'] or 0
    return CaseSearchEndpointVersion.objects.create(
        endpoint=endpoint,
        version_number=last + 1,
        parameters=parameters,
        query=query,
    )
