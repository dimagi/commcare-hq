"""The registry of documented CommCare API resources and views.

``corehq.apps.api.urls`` builds the ``<resource>/v1/`` URL patterns from this
catalogue, and the OpenAPI generator reads the same list, so a resource
cannot be documented without being routed or routed under that scheme
without being documented.

The deprecated ``v0.x`` scheme is routed separately, from
``urls._DEPRECATED_API_LIST``, and names its own resources -- including a few
older classes that exist only to serve it. A resource can therefore be
routed without appearing here; it cannot be *published* without appearing
here.

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

    def base_path(self):
        """The OpenAPI path this resource's list endpoint is published at.

        The one place the scope-to-prefix rule is written down. It used to
        be spelled out at four sites, two of them tests that re-derived it
        with the same expression they were checking -- so a wrong prefix
        would have agreed with itself and passed.

        ``_meta`` is set by tastypie's metaclass at class-creation time, so
        this reads the resource name off the class without instantiating it.
        """
        prefix = '/api' if self.scope == USER else '/a/{domain}/api'
        return (
            f'{prefix}/{self.resource._meta.resource_name}/{self.version}/'
        )


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


@dataclass(frozen=True)
class ViewEntry:
    """One documented function-based API view.

    ``view`` is a dotted ``module:attribute`` path rather than the function
    itself, so importing this module never imports a view module. Only
    ``build_all()`` resolves it.

    No ``scope`` field: unlike ``ApiEntry``, which builds its base URL from
    the scope, a view declares its paths whole, prefix included.
    """

    view: str
    doc_slug: str

    def resolve(self):
        """Import and return the view function this entry names."""
        from django.utils.module_loading import import_string

        return import_string(self.view.replace(':', '.'))


VIEW_CATALOGUE = (
    ViewEntry('corehq.apps.hqcase.views:case_api', 'case-v2'),
    ViewEntry('corehq.apps.hqcase.views:case_api_bulk_fetch', 'case-v2'),
)


def documented_view_entries():
    # Unlike ApiEntry, whose doc_slug may be None (routed but not
    # documented), every ViewEntry is documented by construction, so this
    # filters nothing -- it exists so callers go through one accessor
    # rather than reading VIEW_CATALOGUE directly.
    return list(VIEW_CATALOGUE)


def documented_slugs():
    """Every doc slug the generator produces a per-API spec for.

    Resources and views alike. One registry, so a slug the generator
    writes a spec for cannot be one the serving views reject.
    """
    return {entry.doc_slug for entry in documented_entries()} | {
        entry.doc_slug for entry in documented_view_entries()
    }
