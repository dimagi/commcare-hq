from __future__ import absolute_import, unicode_literals

from django.conf.urls import include, url
from django.http import HttpResponseNotFound

from tastypie.api import Api

from corehq.apps.api import accounting
from corehq.apps.api.domain_metadata import (
    DomainMetadataResource,
    GIRResource,
    MaltResource,
)
from corehq.apps.api.domainapi import DomainAPI
from corehq.apps.api.object_fetch_api import (
    CaseAttachmentAPI,
    FormAttachmentAPI,
)
from corehq.apps.api.odata.views import (
    ODataCaseMetadataView,
    DeprecatedODataCaseMetadataView,
    ODataCaseServiceView,
    DeprecatedODataCaseServiceView,
    DeprecatedODataFormMetadataView,
    DeprecatedODataFormServiceView,
    ODataFormServiceView,
    ODataFormMetadataView,
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
    LookupTableResource,
    LookupTableItemResource,
)
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
        v0_5.DeprecatedODataCaseResource,
        v0_5.DeprecatedODataFormResource,
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
    yield url(r'v0.5/odata/Cases/$', DeprecatedODataCaseServiceView.as_view(), name=DeprecatedODataCaseServiceView.urlname)
    yield url(r'v0.5/odata/Cases/\$metadata$', DeprecatedODataCaseMetadataView.as_view(), name=DeprecatedODataCaseMetadataView.urlname)
    yield url(r'v0.5/odata/Forms/(?P<app_id>[\w\-:]+)/$', DeprecatedODataFormServiceView.as_view(), name=DeprecatedODataFormServiceView.urlname)
    yield url(r'v0.5/odata/Forms/(?P<app_id>[\w\-:]+)/\$metadata$', DeprecatedODataFormMetadataView.as_view(), name=DeprecatedODataFormMetadataView.urlname)
    yield url(r'v0.5/odata/cases/$', ODataCaseServiceView.as_view(), name=ODataCaseServiceView.urlname)
    yield url(r'v0.5/odata/cases/\$metadata$', ODataCaseMetadataView.as_view(), name=ODataCaseMetadataView.urlname)
    yield url(r'v0.5/odata/forms/$', ODataFormServiceView.as_view(), name=ODataFormServiceView.urlname)
    yield url(r'v0.5/odata/forms/\$metadata$', ODataFormMetadataView.as_view(), name=ODataFormMetadataView.urlname)
    for version, resources in API_LIST:
        api = CommCareHqApi(api_name='v%d.%d' % version)
        for R in resources:
            api.register(R())
        yield url(r'^', include(api.urls))
    # HACK: fix circular import here, to fix later
    try:
        from pact.api import PactAPI
    except ImportError:
        pass # maybe pact isn't installed
    for view_class in DomainAPI.__subclasses__():
        yield url(r'^custom/%s/v%s/$' % (view_class.api_name(), view_class.api_version()), view_class.as_view(), name="%s_%s" % (view_class.api_name(), view_class.api_version()))
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
