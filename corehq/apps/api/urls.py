from corehq.apps.api.accounting import *
from corehq.apps.api.domain_metadata import DomainMetadataResource
from corehq.apps.api.object_fetch_api import CaseAttachmentAPI

from corehq.apps.api.domainapi import DomainAPI
from corehq.apps.api.redis_assets import RedisAssetsAPI
from corehq.apps.api.resources import v0_1, v0_2, v0_3, v0_4, v0_5
from corehq.apps.commtrack.resources.v0_1 import ProductResource
from corehq.apps.fixtures.resources.v0_1 import FixtureResource
from corehq.apps.locations import resources as locations
from corehq.apps.reports.resources.v0_1 import ReportResource
from django.conf.urls import *
from django.http import HttpResponseNotFound
from tastypie.api import Api
from corehq.apps.api.es import XFormES


API_LIST = (
    ((0, 1), (
        v0_1.CommCareUserResource,
        v0_1.WebUserResource,
        v0_1.CommCareCaseResource,
        v0_1.XFormInstanceResource,
        FixtureResource,
        ReportResource,
        DomainMetadataResource,
    )),
    ((0, 2), (
        v0_1.CommCareUserResource,
        v0_1.WebUserResource,
        v0_2.CommCareCaseResource,
        v0_1.XFormInstanceResource,
        FixtureResource,
        ReportResource,
        DomainMetadataResource,
    )),
    ((0, 3), (
        v0_1.CommCareUserResource,
        v0_1.WebUserResource,
        v0_3.CommCareCaseResource,
        v0_3.XFormInstanceResource,
        FixtureResource,
        ReportResource,
        DomainMetadataResource,
        locations.v0_1.LocationResource,
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
        ReportResource,
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
        FixtureResource,
        ReportResource,
        v0_5.DeviceReportResource,
        DomainMetadataResource,
        locations.v0_5.LocationResource,
        locations.v0_5.LocationTypeResource,
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
        yield (r'^', include(api.urls))
    yield url(r'^v0.1/xform_es/$', XFormES.as_domain_specific_view())
    # HACK: fix circular import here, to fix later
    try:
        from pact.api import PactAPI
    except ImportError:
        pass # maybe pact isn't installed
    for view_class in DomainAPI.__subclasses__():
        yield url(r'^custom/%s/v%s/$' % (view_class.api_name(), view_class.api_version()), view_class.as_view(), name="%s_%s" % (view_class.api_name(), view_class.api_version()))
    yield url(r'^case/attachment/(?P<case_id>[\w\-]+)/(?P<attachment_id>.*)$', CaseAttachmentAPI.as_view(), name="api_case_attachment")
    yield url(r'^redis_assets/$', RedisAssetsAPI.as_view())


urlpatterns = patterns('', *list(api_url_patterns()))

ADMIN_API_LIST = (
    v0_5.AdminWebUserResource,
    DomainMetadataResource,
    FeatureResource,
    FutureRateResource,
    RoleResource,
    AccountingCurrencyResource,
    SoftwareProductResource,
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
)


def api_url_patterns():
    api = CommCareHqApi(api_name='global')
    for resource in ADMIN_API_LIST:
        api.register(resource())
        yield (r'^', include(api.urls))

admin_urlpatterns = patterns('', *list(api_url_patterns()))
