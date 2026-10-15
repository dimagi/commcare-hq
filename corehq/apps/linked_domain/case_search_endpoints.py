from datetime import datetime

from django.db import IntegrityError, transaction
from django.utils.translation import gettext as _

from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
)
from corehq.apps.linked_domain.exceptions import DomainLinkError


def update_linked_case_search_endpoint(domain_link, upstream_endpoint_id, is_pull=False, overwrite=False):
    if domain_link.is_remote:
        raise DomainLinkError(_("Linking case search endpoints to a remote link is not currently supported"))

    upstream_endpoint = _get_upstream_endpoint(domain_link, upstream_endpoint_id)
    downstream_endpoint = (CaseSearchEndpoint.objects.select_related('current_version')
                           .filter(domain=domain_link.linked_domain, upstream_id=upstream_endpoint.id)
                           .first())
    with transaction.atomic():
        if downstream_endpoint is None:
            _create_downstream_endpoint(domain_link, upstream_endpoint)
        else:
            _update_downstream_endpoint(upstream_endpoint, downstream_endpoint)


def _get_upstream_endpoint(domain_link, endpoint_id):
    try:
        return CaseSearchEndpoint.objects.select_related('current_version').get(
            id=endpoint_id, domain=domain_link.master_domain,
        )
    except CaseSearchEndpoint.DoesNotExist:
        raise DomainLinkError(_("Endpoint does not exist in the upstream domain. Maybe it has been deleted?"))


def _create_downstream_endpoint(domain_link, upstream_endpoint):
    endpoint = CaseSearchEndpoint(
        domain=domain_link.linked_domain,
        name=upstream_endpoint.name,
        target_type=upstream_endpoint.target_type,
        upstream_id=upstream_endpoint.id,
    )
    _sync_active_state(upstream_endpoint, endpoint)
    _save_endpoint(endpoint)
    _copy_current_version(upstream_endpoint, endpoint)


def _update_downstream_endpoint(upstream_endpoint, endpoint):
    endpoint.name = upstream_endpoint.name
    endpoint.target_type = upstream_endpoint.target_type
    _sync_active_state(upstream_endpoint, endpoint)
    _save_endpoint(endpoint, update_fields=[
        'name', 'target_type', 'is_active', 'deactivated_on', 'deactivated_by',
    ])
    _copy_current_version(upstream_endpoint, endpoint)


def _save_endpoint(endpoint, **kwargs):
    try:
        endpoint.save(**kwargs)
    except IntegrityError:
        raise DomainLinkError(_("Endpoint {name} conflicts with an existing endpoint in {domain}")
                              .format(name=endpoint.name, domain=endpoint.domain))


def _sync_active_state(upstream_endpoint, endpoint):
    if upstream_endpoint.is_active:
        endpoint.is_active = True
        endpoint.deactivated_on = None
        endpoint.deactivated_by = ''
    elif endpoint.is_active:
        endpoint.is_active = False
        endpoint.deactivated_on = datetime.utcnow()
        endpoint.deactivated_by = upstream_endpoint.deactivated_by


def _copy_current_version(upstream_endpoint, endpoint):
    upstream_version = upstream_endpoint.current_version
    if upstream_version is None:
        return
    if endpoint.current_version and endpoint.current_version.version_number == upstream_version.version_number:
        return
    fields = ['version_number', 'parameters', 'case_type', 'query', 'dangerous_sql', 'created_by', 'action']
    endpoint.current_version = CaseSearchEndpointVersion.objects.create(
        endpoint=endpoint,
        **{field: getattr(upstream_version, field) for field in fields},
    )
    endpoint.save(update_fields=['current_version'])
