from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.api.accounting import *
from corehq.apps.api.domain_metadata import DomainMetadataResource, MaltResource
from corehq.apps.api.object_fetch_api import CaseAttachmentAPI, FormAttachmentAPI
from corehq.apps.api.domainapi import DomainAPI
from corehq.apps.api.resources import v0_1, v0_3, v0_4, v0_5
from corehq.apps.api.resources.v0_5 import UserDomainsResource, DomainForms, DomainCases, DomainUsernames
from corehq.apps.commtrack.resources.v0_1 import ProductResource
from corehq.apps.fixtures.resources.v0_1 import FixtureResource, InternalFixtureResource
from corehq.apps.locations import resources as locations
from corehq.apps.sms.resources import v0_5 as sms_v0_5
from django.conf.urls import include, url
from django.http import HttpResponseNotFound
from tastypie.api import Api


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
        v0_4.HOPECaseResource,
        FixtureResource,
        DomainMetadataResource,
    )),
    ((0, 5), (
        v0_4.ApplicationResource,
        v0_4.CommCareCaseResource,
        v0_4.XFormInstanceResource,
        v0_4.RepeaterResource,
        v0_4.SingleSignOnResource,
        v0_4.HOPECaseResource,
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
    )),
)


class CommCareHqApi(Api):

    def top_level(self, request, api_name=None, **kwargs):
        return HttpResponseNotFound()


def api_url_patterns():
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
    FeatureResource,
    FeatureRateResource,
    RoleResource,
    AccountingCurrencyResource,
    SoftwarePlanResource,
    DefaultProductPlanResource,
    SoftwareProductRateResource,
    SoftwarePlanVersionResource,
    SubscriberResource,
    BillingAccountResource,
    SubscriptionResource,
    InvoiceResource,
    LineItemResource,
    PaymentMethodResource,
    BillingContactInfoResource,
    PaymentRecordResource,
    CreditLineResource,
    CreditAdjustmentResource,
    SubscriptionAndAdjustmentResource,
    BillingRecordResource,
    MaltResource,
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
