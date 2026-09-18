"""The registry of routed CommCare API resources.

``corehq.apps.api.urls`` builds its URL patterns from this catalogue, and the
OpenAPI generator reads the same list. A resource therefore cannot be routed
without appearing here, and the generated specs cannot describe an endpoint
that is not routed.

Order matters: Django resolves URL patterns in order.
"""

from dataclasses import dataclass

from corehq.apps.api.domain_metadata import DomainMetadataResource
from corehq.apps.api.resources import v0_4, v0_5, v1_0
from corehq.apps.api.resources.v0_5 import (
    DomainCases,
    DomainForms,
    DomainUsernames,
    UserDomainsResource,
)
from corehq.apps.fixtures import resources as fixtures
from corehq.apps.locations import resources as locations

DOMAIN = 'domain'
USER = 'user'


@dataclass(frozen=True)
class ApiEntry:
    """One routed resource version.

    ``doc_slug`` is the basename of the generated spec document, or ``None``
    for resources that are routed but not publicly documented. Several
    documentation pages may render from one spec.
    """

    resource: type
    version: str
    doc_slug: str | None = None
    scope: str = DOMAIN


CATALOGUE = (
    ApiEntry(v0_4.ApplicationResource, 'v1', 'application-v1'),
    ApiEntry(v0_4.CommCareCaseResource, 'v1', 'case-v1'),
    ApiEntry(v0_4.XFormInstanceResource, 'v1', 'form-v1'),
    ApiEntry(v0_4.SingleSignOnResource, 'v1', 'sso-v1'),
    ApiEntry(v0_5.CommCareUserResource, 'v1', 'user-v1'),
    ApiEntry(v0_5.WebUserResource, 'v1', 'web-user-v1'),
    ApiEntry(v0_5.GroupResource, 'v1', 'group-v1'),
    ApiEntry(v0_5.BulkUserResource, 'v1', 'bulk-user-v1'),
    ApiEntry(fixtures.v0_1.InternalFixtureResource, 'v1'),
    ApiEntry(fixtures.v0_1.FixtureResource, 'v1', 'fixture-v1'),
    ApiEntry(v0_5.DeviceReportResource, 'v1'),
    ApiEntry(DomainMetadataResource, 'v1'),
    ApiEntry(locations.v0_5.LocationResource, 'v1', 'location-v1'),
    ApiEntry(locations.v0_6.LocationResource, 'v2', 'location-v2'),
    ApiEntry(locations.v0_5.LocationTypeResource, 'v1', 'location-type-v1'),
    ApiEntry(v0_5.SimpleReportConfigurationResource, 'v1', 'report-config-v1'),
    ApiEntry(v0_5.ConfigurableReportDataResource, 'v1', 'report-data-v1'),
    ApiEntry(v0_5.DataSourceConfigurationResource, 'v1'),
    ApiEntry(DomainForms, 'v1'),
    ApiEntry(DomainCases, 'v1'),
    ApiEntry(DomainUsernames, 'v1'),
    ApiEntry(locations.v0_1.InternalLocationResource, 'v1'),
    ApiEntry(v0_5.ODataCaseResource, 'v1'),
    ApiEntry(v0_5.ODataFormResource, 'v1'),
    ApiEntry(fixtures.v0_1.LookupTableResource, 'v1', 'lookup-table-v1'),
    ApiEntry(
        fixtures.v0_1.LookupTableItemResource, 'v1', 'lookup-table-item-v1'
    ),
    ApiEntry(
        fixtures.v0_6.LookupTableItemResource, 'v2', 'lookup-table-item-v2'
    ),
    ApiEntry(v0_5.NavigationEventAuditResource, 'v1'),
    ApiEntry(v1_0.CommCareAnalyticsUserResource, 'v1'),
    ApiEntry(v1_0.InvitationResource, 'v1'),
    ApiEntry(v1_0.DETExportInstanceResource, 'v1', 'det-export-v1'),
    ApiEntry(v0_5.IdentityResource, 'v1', scope=USER),
    ApiEntry(UserDomainsResource, 'v1', 'user-domains-v1', scope=USER),
)


def entries_for_scope(scope):
    return [entry for entry in CATALOGUE if entry.scope == scope]


def documented_entries():
    return [entry for entry in CATALOGUE if entry.doc_slug]
