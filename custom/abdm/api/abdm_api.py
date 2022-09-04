from tastypie.resources import ModelResource
from custom.abdm.model.abdm_model import Product, Order
from custom.abdm.auth.abdm_auth import CustomApiKeyAuthentication


class ProductResource(ModelResource):

    class Meta:
        queryset = Product.objects.all()
        resource_name = 'product'
        excludes = ["product_type", "price"]
        allowed_methods = ['get']
        authentication = CustomApiKeyAuthentication()


class OrderResource(ModelResource):

    class Meta:
        queryset = Order.objects.all()
        resource_name = 'order'
        allowed_methods = ['get', 'post', 'put']
        authentication = CustomApiKeyAuthentication()