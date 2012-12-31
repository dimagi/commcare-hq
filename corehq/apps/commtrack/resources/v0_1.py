from tastypie import fields
from corehq.apps.api.resources.v0_1 import CustomResourceMeta
from corehq.apps.commtrack.models import Product
from corehq.apps.api.util import get_object_or_not_exist
from corehq.apps.api.resources import JsonResource

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
