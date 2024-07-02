from tastypie.api import Api
from corehq.apps.enterprise.api.resources import DomainResource

v1_api = Api(api_name='v1')
v1_api.register(DomainResource())
