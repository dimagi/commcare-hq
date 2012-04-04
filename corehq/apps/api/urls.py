from corehq.apps.api.resources import CommCareUserResource, CommCareCaseResource
from django.conf.urls.defaults import *
from tastypie.api import Api

v0_1_api = Api(api_name=r'v0\.1')
v0_1_api.register(CommCareUserResource())
v0_1_api.register(CommCareCaseResource())

urlpatterns = patterns('',
    (r'^', include(v0_1_api.urls)),
)