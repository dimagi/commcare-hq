from tastypie import fields

from corehq.apps.api.resources import HqBaseResource
from corehq.apps.api.resources.auth import DomainAdminAuthentication
from corehq.apps.api.resources.meta import CustomResourceMeta
from corehq.apps.api.util import object_does_not_exist
from corehq.apps.products.models import SQLProduct


"""
Implementation of the CommCare Supply APIs. For more information see:

https://confluence.dimagi.com/display/lmis/API
"""


class ProductResource(HqBaseResource):

    type = "product"
    id = fields.CharField(attribute='product_id', readonly=True, unique=True)
    code = fields.CharField(attribute='code', readonly=True, unique=True)
    name = fields.CharField(attribute='name', readonly=True)
    unit = fields.CharField(attribute='units', readonly=True, null=True)
    description = fields.CharField(attribute='description', readonly=True, null=True)
    category = fields.CharField(attribute='category', readonly=True, null=True)
    last_modified = fields.DateTimeField(attribute='last_modified', readonly=True, null=True)

    def obj_get(self, request, **kwargs):
        try:
            SQLProduct.objects.get(product_id=kwargs['pk'], domain=kwargs['domain'])
        except SQLProduct.DoesNotExist:
            raise object_does_not_exist("Product", kwargs['pk'])

    def obj_get_list(self, request, **kwargs):
        return SQLProduct.active_objects.filter(domain=kwargs['domain'])

    class Meta(CustomResourceMeta):
        authentication = DomainAdminAuthentication()
        resource_name = 'product'
        limit = 0
