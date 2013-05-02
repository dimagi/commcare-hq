from tastypie import fields
from corehq.apps.api.resources.v0_1 import CustomResourceMeta
from corehq.apps.commtrack.models import Product, StockStatus,\
    StockTransaction, StockReport
from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.api.resources import JsonResource
from casexml.apps.case.models import CommCareCase
from tastypie.bundle import Bundle

"""
Implementation of the CommTrack APIs. For more information see:

https://confluence.dimagi.com/display/lmis/API
"""

class ProductResource(JsonResource):

    type = "product"
    id  = fields.CharField(attribute='_id', readonly=True, unique=True)
    code = fields.CharField(attribute='code', readonly=True, unique=True)
    name = fields.CharField(attribute='name', readonly=True)
    unit = fields.CharField(attribute='unit', readonly=True, null=True)
    description = fields.CharField(attribute='description', readonly=True, null=True)
    category = fields.CharField(attribute='category', readonly=True, null=True)
    # TODO:
    # price? last_modified?

    def obj_get(self, request, **kwargs):
        return get_object_or_not_exist(Product, kwargs['pk'], kwargs['domain'])

    def obj_get_list(self, request, **kwargs):
        return Product.by_domain(kwargs['domain'])

    class Meta(CustomResourceMeta):
        resource_name = 'product'
        limit = 0

class StockStatusResource(JsonResource):

    type = "stock_status"
    id = fields.CharField(attribute='_id', readonly=True, unique=True)
    current_stock = fields.IntegerField(attribute='current_stock', readonly=True, null=True)
    stocked_out_since = fields.DateTimeField(attribute='stocked_out_since', readonly=True, null=True)
    product_id = fields.CharField(attribute='product', readonly=True)
    location_id = fields.CharField(attribute='location_id', readonly=True)
    modified_on = fields.DateTimeField(attribute='server_modified_on', readonly=True, null=True)

    def obj_get(self, request, **kwargs):
        case = get_object_or_not_exist(CommCareCase, kwargs["pk"], kwargs["domain"])
        return StockStatus.from_case(case)

    def obj_get_list(self, request, **kwargs):
        location_id = request.GET.get("location_id", None)
        if location_id:
            return StockStatus.by_location(kwargs['domain'], location_id)
        else:
            return StockStatus.by_domain(kwargs['domain'])

    class Meta(CustomResourceMeta):
        resource_name = 'stock_status'

class StockTransactionResource(JsonResource):
    type = "stock_transaction"
    product_id = fields.CharField(attribute='product', readonly=True)
    product_entry_id = fields.CharField(attribute='product_entry', readonly=True)
    action = fields.CharField(attribute='action', readonly=True)
    value = fields.IntegerField(attribute='value', readonly=True)
    inferred = fields.BooleanField(attribute='inferred', readonly=True)

    def obj_get(self, request, **kwargs):
        raise NotImplementedError()

    def obj_get_list(self, request, **kwargs):
        location_id = request.GET.get("location_id", None)
        if location_id:
            return StockTransaction.by_location(kwargs['domain'], location_id)
        else:
            return StockTransaction.by_domain(kwargs['domain'])

    class Meta(CustomResourceMeta):
        resource_name = 'stock_transaction'

class FullStockTransactionResource(StockTransactionResource):
    """
    This is the one that's actually used in the stock transaction API,
    since it adds other fields from the stock report.
    """
    location_id = fields.CharField(attribute='location_id', readonly=True)
    received_on = fields.DateTimeField(attribute='received_on', readonly=True)

class ManualRelatedField(fields.RelatedField):
    def __init__(self, *args, **kwargs):
        super(ManualRelatedField, self).__init__(*args, **kwargs)
        self.full = True

    def dehydrate(self, bundle):
        data = getattr(bundle.obj, self.attribute)
        self.m2m_resources = []
        m2m_dehydrated = []

        for m2m in data:
            m2m_resource = self.get_related_resource(m2m)
            m2m_bundle = Bundle(obj=m2m, request=bundle.request)
            self.m2m_resources.append(m2m_resource)
            m2m_dehydrated.append(self.dehydrate_related(m2m_bundle, m2m_resource))

        return m2m_dehydrated

class StockReportResource(JsonResource):
    type = "stock_report"
    id  = fields.CharField(attribute='id', readonly=True, unique=True)
    user_id = fields.CharField(attribute='user_id', readonly=True, unique=True)
    location_id = fields.CharField(attribute='location_id', readonly=True)
    submitted_on = fields.DateTimeField(attribute='submitted_on', readonly=True, null=True)
    received_on = fields.DateTimeField(attribute='received_on', readonly=True, null=True)
    transactions = ManualRelatedField(StockTransactionResource, 'transactions')

    def obj_get(self, request, **kwargs):
        raise NotImplementedError()

    def obj_get_list(self, request, **kwargs):
        return StockReport.get_reports(kwargs['domain'])

    class Meta(CustomResourceMeta):
        resource_name = 'stock_report'
        limit = 0
