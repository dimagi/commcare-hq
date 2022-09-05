from tastypie.resources import Resource
from custom.abdm.auth.abdm_auth import CustomApiKeyAuthentication


class ProductResource(Resource):

    def obj_create(self, bundle, request=None, **kwargs):
        print("in obj_create")
        return bundle

    def obj_update(self, bundle, **kwargs):
        print("in obj_update")
        return bundle

    class Meta:
        authentication = CustomApiKeyAuthentication()
        object_class = Repeater
        resource_name = 'data-forwarding'
        detail_allowed_methods = ['post', 'get', 'put']
