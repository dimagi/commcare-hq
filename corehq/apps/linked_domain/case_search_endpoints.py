from django.db import transaction
from django.utils.translation import gettext as _

from corehq.apps.case_search.models import (
    CaseSearchEndpoint,
    CaseSearchEndpointVersion,
    add_endpoint_version,
)
from corehq.apps.linked_domain.exceptions import DomainLinkError

VERSION_FIELDS = ['case_type', 'query', 'parameters', 'dangerous_sql']


def create_linked_case_search_endpoint(domain_link, endpoint_id):
    if domain_link.is_remote:
        raise DomainLinkError(
            _("Linking case search endpoints to a remote link is not currently supported")
        )

    upstream_endpoint = _get_upstream_endpoint(domain_link, endpoint_id)

    if CaseSearchEndpoint.objects.filter(
        name=upstream_endpoint.name,
        domain=domain_link.linked_domain,
    ).exists():
        raise DomainLinkError(
            _("Endpoint {name} already exists in the downstream domain {domain}").format(
                name=upstream_endpoint.name, domain=domain_link.linked_domain,
            )
        )

    with transaction.atomic():
        endpoint = CaseSearchEndpoint.objects.create(
            domain=domain_link.linked_domain,
            name=upstream_endpoint.name,
            target_type=upstream_endpoint.target_type,
            is_active=upstream_endpoint.is_active,
            upstream_id=upstream_endpoint.id,
        )
        _copy_version(domain_link, upstream_endpoint, endpoint, CaseSearchEndpointVersion.Action.CREATE)

    return endpoint.id


def update_linked_case_search_endpoint(domain_link, endpoint_id, is_pull=False, overwrite=False):
    try:
        endpoint = CaseSearchEndpoint.objects.select_related('current_version').get(id=endpoint_id)
    except CaseSearchEndpoint.DoesNotExist:
        raise DomainLinkError(_("Linked endpoint could not be found"))

    upstream_endpoint = _get_upstream_endpoint(domain_link, endpoint.upstream_id)

    with transaction.atomic():
        endpoint.name = upstream_endpoint.name
        endpoint.target_type = upstream_endpoint.target_type
        endpoint.is_active = upstream_endpoint.is_active
        endpoint.save(update_fields=['name', 'target_type', 'is_active'])
        if not _version_matches(upstream_endpoint.current_version, endpoint.current_version):
            _copy_version(
                domain_link, upstream_endpoint, endpoint, CaseSearchEndpointVersion.Action.UPDATE,
            )


def _get_upstream_endpoint(domain_link, endpoint_id):
    try:
        return CaseSearchEndpoint.objects.select_related('current_version').get(
            id=endpoint_id, domain=domain_link.master_domain,
        )
    except CaseSearchEndpoint.DoesNotExist:
        raise DomainLinkError(
            _("Endpoint does not exist in the upstream domain. Maybe it has been deleted?")
        )


def _version_matches(upstream_version, downstream_version):
    if upstream_version is None or downstream_version is None:
        return upstream_version is downstream_version
    return all(
        getattr(upstream_version, field) == getattr(downstream_version, field)
        for field in VERSION_FIELDS
    )


def _copy_version(domain_link, upstream_endpoint, endpoint, action):
    """Record the upstream endpoint's current content as a new downstream version.

    Downstream version numbering is independent of the upstream's, since a
    downstream endpoint is only updated when it is pushed or pulled.
    """
    upstream_version = upstream_endpoint.current_version
    if upstream_version is None:
        return
    add_endpoint_version(
        endpoint,
        action=action,
        created_by=f'{domain_link.master_domain} (upstream)',
        **{field: getattr(upstream_version, field) for field in VERSION_FIELDS},
    )
