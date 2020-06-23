from django.conf.urls import include, url
from django.http import HttpResponseNotFound

from tastypie.api import Api

from corehq.apps.api import accounting
from corehq.apps.api.domain_metadata import (
    DomainMetadataResource,
    GIRResource,
    MaltResource,
)
from corehq.apps.api.object_fetch_api import (
    CaseAttachmentAPI,
    FormAttachmentAPI,
)
from corehq.apps.api.odata.views import (
    ODataCaseMetadataView,
    ODataCaseServiceView,
    ODataFormMetadataView,
    ODataFormServiceView,
)
from corehq.apps.api.resources import v0_1, v0_3, v0_4, v0_5
from corehq.apps.api.resources.v0_5 import (
    DomainCases,
    DomainForms,
    DomainUsernames,
    UserDomainsResource,
)
from corehq.apps.commtrack.resources.v0_1 import ProductResource
from corehq.apps.fixtures.resources.v0_1 import (
    FixtureResource,
    InternalFixtureResource,
    LookupTableItemResource,
    LookupTableResource,
)
from corehq.apps.hqwebapp.decorators import waf_allow
from corehq.apps.locations import resources as locations
from corehq.apps.sms.resources import v0_5 as sms_v0_5

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
        v0_4.RepeaterResource,
        v0_4.SingleSignOnResource,
        FixtureResource,
        DomainMetadataResource,
    )),
    ((0, 5), (
        v0_4.ApplicationResource,
        v0_4.CommCareCaseResource,
        v0_4.XFormInstanceResource,
        v0_4.RepeaterResource,
        v0_4.SingleSignOnResource,
        v0_5.CommCareUserResource,
        v0_5.WebUserResource,
        v0_5.GroupResource,
        v0_5.BulkUserResource,
        v0_5.StockTransactionResource,
        InternalFixtureResource,
        FixtureResource,
        v0_5.DeviceReportResource,
        DomainMetadataResource,
        locations.v0_5.LocationResource,
        locations.v0_5.LocationTypeResource,
        v0_5.SimpleReportConfigurationResource,
        v0_5.ConfigurableReportDataResource,
        DomainForms,
        DomainCases,
        DomainUsernames,
        sms_v0_5.UserSelfRegistrationResource,
        sms_v0_5.UserSelfRegistrationReinstallResource,
        locations.v0_1.InternalLocationResource,
        v0_5.ODataCaseResource,
        v0_5.ODataFormResource,
        LookupTableResource,
        LookupTableItemResource,
    )),
)


class CommCareHqApi(Api):

    def top_level(self, request, api_name=None, **kwargs):
        return HttpResponseNotFound()


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
    for version, resources in API_LIST:
        api = CommCareHqApi(api_name='v%d.%d' % version)
        for R in resources:
            api.register(R())
        yield url(r'^', include(api.urls))
    yield url(r'^case/attachment/(?P<case_id>[\w\-:]+)/(?P<attachment_id>.*)$', CaseAttachmentAPI.as_view(), name="api_case_attachment")
    yield url(r'^form/attachment/(?P<form_id>[\w\-:]+)/(?P<attachment_id>.*)$', FormAttachmentAPI.as_view(), name="api_form_attachment")


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


USER_API_LIST = (
    UserDomainsResource,
)


def api_url_patterns():
    api = CommCareHqApi(api_name='global')
    for resource in ADMIN_API_LIST + USER_API_LIST:
        api.register(resource())
        yield url(r'^', include(api.urls))


admin_urlpatterns = list(api_url_patterns())


waf_allow('XSS_BODY', hard_code_pattern=r'^/a/([\w\.:-]+)/api/v([\d\.]+)/form/$')
