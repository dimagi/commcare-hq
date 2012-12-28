from tastypie import fields
from corehq.apps.api.resources.v0_1 import CustomResourceMeta
from corehq.apps.commtrack.models import Product, StockStatus,\
    StockTransaction
from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.api.resources import JsonResource
from casexml.apps.case.models import CommCareCase

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
    id = fields.CharField(attribute='id', readonly=True, unique=True)
    current_stock = fields.IntegerField(attribute='current_stock', readonly=True, null=True)
    stocked_out_since = fields.DateTimeField(attribute='stocked_out_since', readonly=True, null=True)
    product_id = fields.CharField(attribute='product_id', readonly=True)
    location_id = fields.CharField(attribute='location_id', readonly=True)
    modified_on = fields.DateTimeField(attribute='modified_on', readonly=True, null=True)

    def obj_get(self, request, **kwargs):
        case = get_object_or_not_exist(CommCareCase, kwargs["pk"], kwargs["domain"])
        return StockStatus.from_case(case)

    def obj_get_list(self, request, **kwargs):
        return StockStatus.by_domain(kwargs['domain'])

    class Meta(CustomResourceMeta):
        resource_name = 'stock_status'

class StockTransactionResource(JsonResource):
    type = "stock_transaction"
    value = fields.IntegerField(attribute='value', readonly=True)
    action = fields.CharField(attribute='action', readonly=True)
    product_id = fields.CharField(attribute='product_id', readonly=True)
    location_id = fields.CharField(attribute='location_id', readonly=True)
    product_entry_id = fields.CharField(attribute='product_entry_id', readonly=True)
    received_on = fields.DateTimeField(attribute='received_on', readonly=True)
    inferred = fields.BooleanField(attribute='inferred', readonly=True)

    def obj_get(self, request, **kwargs):
        raise NotImplementedError()

    def obj_get_list(self, request, **kwargs):
        return StockTransaction.by_domain(kwargs['domain'])

    class Meta(CustomResourceMeta):
        resource_name = 'stock_transaction'

# TODO: tweak this and get it working
#class StockReportResource(JsonResource):
#
#    type = "stock_report"
#    id  = fields.CharField(attribute='id', readonly=True, unique=True)
#    current_stock = fields.IntegerField(attribute='current_stock', readonly=True, null=True)
#    stocked_out_since = fields.DateTimeField(attribute='stocked_out_since', readonly=True, null=True)
#    product_id = fields.CharField(attribute='product_id', readonly=True)
#    location_id = fields.CharField(attribute='location_id', readonly=True)
#    description = fields.CharField(attribute='description', readonly=True, null=True)
#    modified_on = fields.DateTimeField(attribute='modified_on', readonly=True, null=True)
#
#    def obj_get(self, request, **kwargs):
#        return get_object_or_not_exist(Product, kwargs['pk'], kwargs['domain'])
#
#    def obj_get_list(self, request, **kwargs):
#        return StockReport.get_reports(kwargs['domain'])
#
#    class Meta(CustomResourceMeta):
#        resource_name = 'stock_report'
#        limit = 0
