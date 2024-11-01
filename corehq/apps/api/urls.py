"""
The CommCareHQ API is comprised of resources, representing individual data
models. Each resource may contain multiple endpoints (list, detail, etc), and
may have multiple versions.

Historically, resources were versioned together, so making a backwards
incompatible change to one required bumping the version for everything. This
was our standard up through API version 0.6. URLS looked like this:

    /a/mydomain/api/v0.5/user/

In 2024 we switched to versioning resources independently and dropped the minor
versioning, such that new URLs look like this, with the resource name first:

    /a/mydomain/api/user/v1/

To manage the transition, all v0.5 URls are duplicated as v1, and v0.6 URLs are
duplicated as v2.

Additive and otherwise backwards-compatible changes can be done without bumping
versions. This includes things like adding a new field or filter parameter, as
we don't expect such changes to disrupt existing integrations. To introduce
breaking changes, make the new version of the resource available at the next
version number up.
"""
from django.http import HttpResponseNotFound
from django.urls import include, path
from django.urls import re_path as url

from tastypie.api import Api

from corehq.apps.api import accounting
from corehq.apps.api.domain_metadata import (
    DomainMetadataResource,
    GIRResource,
    MaltResource,
)
from corehq.apps.api.object_fetch_api import (
    CaseAttachmentAPI,
    view_form_attachment,
)
from corehq.apps.api.odata.urls import (
    odata_case_urlpatterns,
    odata_form_urlpatterns,
)
from corehq.apps.api.resources import v0_1, v0_3, v0_4, v0_5
from corehq.apps.api.resources.messaging_event.view import messaging_events
from corehq.apps.api.resources.v0_5 import (
    DomainCases,
    DomainForms,
    DomainUsernames,
    UserDomainsResource,
)
from corehq.apps.commtrack.resources.v0_1 import ProductResource
from corehq.apps.fixtures import resources as fixtures
from corehq.apps.hqcase.views import case_api, case_api_bulk_fetch
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.locations import resources as locations
from corehq.motech.generic_inbound.views import generic_inbound_api

_OLD_API_LIST = (
    ((0, 3), (
        v0_3.CommCareCaseResource,
        ProductResource,
    )),
    ((0, 4), (
        v0_1.CommCareUserResource,
        v0_1.WebUserResource,
        v0_4.ApplicationResource,
        v0_4.CommCareCaseResource,
        v0_4.GroupResource,
        v0_4.XFormInstanceResource,
        v0_4.SingleSignOnResource,
        fixtures.v0_1.FixtureResource,
        DomainMetadataResource,
    )),
    ((0, 5), (
        v0_4.ApplicationResource,
        v0_4.CommCareCaseResource,
        v0_4.XFormInstanceResource,
        v0_4.SingleSignOnResource,
        v0_5.CommCareUserResource,
        v0_5.WebUserResource,
        v0_5.GroupResource,
        v0_5.BulkUserResource,
        fixtures.v0_1.InternalFixtureResource,
        fixtures.v0_1.FixtureResource,
        v0_5.DeviceReportResource,
        DomainMetadataResource,
        locations.v0_5.LocationResource,
        locations.v0_5.LocationTypeResource,
        v0_5.SimpleReportConfigurationResource,
        v0_5.ConfigurableReportDataResource,
        v0_5.DataSourceConfigurationResource,
        DomainForms,
        DomainCases,
        DomainUsernames,
        locations.v0_1.InternalLocationResource,
        v0_5.ODataCaseResource,
        v0_5.ODataFormResource,
        fixtures.v0_1.LookupTableResource,
        fixtures.v0_1.LookupTableItemResource,
        v0_5.NavigationEventAuditResource,
        v0_5.CommCareAnalyticsUserResource,
    )),
    ((0, 6), (
        locations.v0_6.LocationResource,
        fixtures.v0_6.LookupTableItemResource,
    ))
)


class CommCareHqApi(Api):

    def top_level(self, request, api_name=None, **kwargs):
        return HttpResponseNotFound()


def versioned_apis(api_list):
    for version, resources in api_list:
        api_name = 'v%d.%d' % version
        api = CommCareHqApi(api_name=api_name)
        for R in resources:
            api.register(R(api_name))
        yield url(r'^', include(api.urls))


urlpatterns = [
    url(r'(?P<api_version>v0.5)/odata/cases/', include(odata_case_urlpatterns)),
    url(r'(?P<api_version>v0.5)/odata/forms/', include(odata_form_urlpatterns)),
    url(r'odata/cases/(?P<api_version>v1)/', include(odata_case_urlpatterns)),
    url(r'odata/forms/(?P<api_version>v1)/', include(odata_form_urlpatterns)),

    url(r'(?P<api_version>v0.5)/messaging-event/$',
        messaging_events, name="api_messaging_event_list"),
    url(r'(?P<api_version>v0.5)/messaging-event/(?P<event_id>\d+)/$',
        messaging_events, name="api_messaging_event_detail"),
    url(r'messaging-event/(?P<api_version>v1)/$',
        messaging_events, name="api_messaging_event_list"),
    url(r'messaging-event/(?P<api_version>v1)/(?P<event_id>\d+)/$',
        messaging_events, name="api_messaging_event_detail"),
    url(r'v0\.6/case/bulk-fetch/$', case_api_bulk_fetch),
    url(r'case/v2/bulk-fetch/$', case_api_bulk_fetch, name='case_api_bulk_fetch'),
    # match v0.6/case/ AND v0.6/case/e0ad6c2e-514c-4c2b-85a7-da35bbeb1ff1/ trailing slash optional
    url(r'v0\.6/case(?:/(?P<case_id>[\w\-,]+))?/?$', case_api),
    url(r'case/v2(?:/(?P<case_id>[\w\-,]+))?/?$', case_api, name='case_api'),
    path('', include(list(versioned_apis(_OLD_API_LIST)))),
    url(r'^case/attachment/(?P<case_id>[\w\-:]+)/(?P<attachment_id>.*)$', CaseAttachmentAPI.as_view()),
    url(r'^case_attachment/v1/(?P<case_id>[\w\-:]+)/(?P<attachment_id>.*)$', CaseAttachmentAPI.as_view(),
        name="api_case_attachment"),
    url(r'^form/attachment/(?P<instance_id>[\w\-:]+)/(?P<attachment_id>.*)$', view_form_attachment),
    url(r'^form_attachment/v1/(?P<instance_id>[\w\-:]+)/(?P<attachment_id>.*)$', view_form_attachment,
        name="api_form_attachment"),
    path('case/custom/<slug:api_id>/', generic_inbound_api, name="generic_inbound_api"),
    url(r'(?P<api_version>v0.5)/ucr/', v0_5.get_ucr_data, name="api_get_ucr_data"),
    url(r'ucr/(?P<api_version>v1)/', v0_5.get_ucr_data, name="api_get_ucr_data"),
    v0_4.ApplicationResource.get_urlpattern('v1'),
    v0_4.CommCareCaseResource.get_urlpattern('v1'),
    v0_4.XFormInstanceResource.get_urlpattern('v1'),
    v0_4.SingleSignOnResource.get_urlpattern('v1'),
    v0_5.CommCareUserResource.get_urlpattern('v1'),
    v0_5.WebUserResource.get_urlpattern('v1'),
    v0_5.GroupResource.get_urlpattern('v1'),
    v0_5.BulkUserResource.get_urlpattern('v1'),
    fixtures.v0_1.InternalFixtureResource.get_urlpattern('v1'),
    fixtures.v0_1.FixtureResource.get_urlpattern('v1'),
    v0_5.DeviceReportResource.get_urlpattern('v1'),
    DomainMetadataResource.get_urlpattern('v1'),
    locations.v0_5.LocationResource.get_urlpattern('v1'),
    locations.v0_6.LocationResource.get_urlpattern('v2'),
    locations.v0_5.LocationTypeResource.get_urlpattern('v1'),
    v0_5.SimpleReportConfigurationResource.get_urlpattern('v1'),
    v0_5.ConfigurableReportDataResource.get_urlpattern('v1'),
    v0_5.DataSourceConfigurationResource.get_urlpattern('v1'),
    DomainForms.get_urlpattern('v1'),
    DomainCases.get_urlpattern('v1'),
    DomainUsernames.get_urlpattern('v1'),
    locations.v0_1.InternalLocationResource.get_urlpattern('v1'),
    v0_5.ODataCaseResource.get_urlpattern('v1'),
    v0_5.ODataFormResource.get_urlpattern('v1'),
    fixtures.v0_1.LookupTableResource.get_urlpattern('v1'),
    fixtures.v0_1.LookupTableItemResource.get_urlpattern('v1'),
    fixtures.v0_6.LookupTableItemResource.get_urlpattern('v2'),
    v0_5.NavigationEventAuditResource.get_urlpattern('v1'),
]


ADMIN_API_LIST = (
    v0_5.AdminWebUserResource,
    DomainMetadataResource,
    accounting.FeatureResource,
    accounting.FeatureRateResource,
    accounting.RoleResource,
    accounting.AccountingCurrencyResource,
    accounting.SoftwarePlanResource,
    accounting.DefaultProductPlanResource,
    accounting.SoftwareProductRateResource,
    accounting.SoftwarePlanVersionResource,
    accounting.SubscriberResource,
    accounting.BillingAccountResource,
    accounting.SubscriptionResource,
    accounting.InvoiceResource,
    accounting.CustomerInvoiceResource,
    accounting.LineItemResource,
    accounting.PaymentMethodResource,
    accounting.BillingContactInfoResource,
    accounting.PaymentRecordResource,
    accounting.CreditLineResource,
    accounting.CreditAdjustmentResource,
    accounting.SubscriptionAndAdjustmentResource,
    accounting.BillingRecordResource,
    MaltResource,
    GIRResource,
    UserDomainsResource,
)


def _get_global_api_url_patterns(resources):
    api = CommCareHqApi(api_name='global')
    for resource in resources:
        api.register(resource())
    return url(r'^', include(api.urls))


admin_urlpatterns = [_get_global_api_url_patterns(ADMIN_API_LIST)]

# Not domain-scoped
VERSIONED_USER_API_LIST = (
    ((0, 5), (
        v0_5.IdentityResource,
        UserDomainsResource,
    )),
)

user_urlpatterns = [
    path('', include(list(versioned_apis(VERSIONED_USER_API_LIST)))),
    v0_5.IdentityResource.get_urlpattern('v1'),
    UserDomainsResource.get_urlpattern('v1'),
]

waf_allow('XSS_BODY', hard_code_pattern=r'^/a/([\w\.:-]+)/api/v([\d\.]+)/form/$')
