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
from corehq.apps.api.odata.views import (
    ODataCaseMetadataView,
    ODataCaseServiceView,
    ODataFormMetadataView,
    ODataFormServiceView,
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

API_LIST = (
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
        api = CommCareHqApi(api_name='v%d.%d' % version)
        for R in resources:
            api.register(R())
        yield url(r'^', include(api.urls))


def api_url_patterns():
    # todo: these have to come first to short-circuit tastypie's matching
    yield url(r'v0.5/odata/cases/(?P<config_id>[\w\-:]+)/(?P<table_id>[\d]+)/$',
              ODataCaseServiceView.as_view(), name=ODataCaseServiceView.table_urlname)
    yield url(r'v0.5/odata/cases/(?P<config_id>[\w\-:]+)/$',
              ODataCaseServiceView.as_view(), name=ODataCaseServiceView.urlname)
    yield url(r'v0.5/odata/cases/(?P<config_id>[\w\-:]+)/(?P<table_id>[\d]+)/\$metadata$',
              ODataCaseMetadataView.as_view(), name=ODataCaseMetadataView.table_urlname)
    yield url(r'v0.5/odata/cases/(?P<config_id>[\w\-:]+)/\$metadata$',
              ODataCaseMetadataView.as_view(), name=ODataCaseMetadataView.urlname)

    yield url(r'v0.5/odata/forms/(?P<config_id>[\w\-:]+)/(?P<table_id>[\d]+)/$',
              ODataFormServiceView.as_view(), name=ODataFormServiceView.table_urlname)
    yield url(r'v0.5/odata/forms/(?P<config_id>[\w\-:]+)/$',
              ODataFormServiceView.as_view(), name=ODataFormServiceView.urlname)
    yield url(r'v0.5/odata/forms/(?P<config_id>[\w\-:]+)/(?P<table_id>[\d]+)/\$metadata$',
              ODataFormMetadataView.as_view(), name=ODataFormMetadataView.table_urlname)
    yield url(r'v0.5/odata/forms/(?P<config_id>[\w\-:]+)/\$metadata$',
              ODataFormMetadataView.as_view(), name=ODataFormMetadataView.urlname)
    yield url(r'v0.5/messaging-event/$', messaging_events, name="api_messaging_event_list")
    yield url(r'v0.5/messaging-event/(?P<event_id>\d+)/$', messaging_events, name="api_messaging_event_detail")
    yield url(r'v0\.6/case/bulk-fetch/$', case_api_bulk_fetch, name='case_api_bulk_fetch')
    # match v0.6/case/ AND v0.6/case/e0ad6c2e-514c-4c2b-85a7-da35bbeb1ff1/ trailing slash optional
    yield url(r'v0\.6/case(?:/(?P<case_id>[\w\-,]+))?/?$', case_api, name='case_api')
    yield from versioned_apis(API_LIST)
    yield url(r'^case/attachment/(?P<case_id>[\w\-:]+)/(?P<attachment_id>.*)$', CaseAttachmentAPI.as_view(),
              name="api_case_attachment")
    yield url(r'^form/attachment/(?P<instance_id>[\w\-:]+)/(?P<attachment_id>.*)$', view_form_attachment,
              name="api_form_attachment")

    yield path('case/custom/<slug:api_id>/', generic_inbound_api, name="generic_inbound_api")
    yield url(r'v0.5/ucr/', v0_5.get_ucr_data, name="api_get_ucr_data")


urlpatterns = list(api_url_patterns())

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
)


# these APIs are duplicated to /hq/admin/global for backwards compatibility
GLOBAL_USER_API_LIST = (
    UserDomainsResource,
)

NON_GLOBAL_USER_API_LIST = (
    v0_5.IdentityResource,
)


USER_API_LIST = GLOBAL_USER_API_LIST + NON_GLOBAL_USER_API_LIST


def _get_global_api_url_patterns(resources):
    api = CommCareHqApi(api_name='global')
    for resource in resources:
        api.register(resource())
    return url(r'^', include(api.urls))


admin_urlpatterns = [
    _get_global_api_url_patterns(ADMIN_API_LIST),
    _get_global_api_url_patterns(GLOBAL_USER_API_LIST),
]


VERSIONED_USER_API_LIST = (
    ((0, 5), USER_API_LIST),
)


user_urlpatterns = list(versioned_apis(VERSIONED_USER_API_LIST))

waf_allow('XSS_BODY', hard_code_pattern=r'^/a/([\w\.:-]+)/api/v([\d\.]+)/form/$')
