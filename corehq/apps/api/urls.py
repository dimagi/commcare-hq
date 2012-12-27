from corehq.apps.api.resources import v0_1, v0_2, v0_3
from corehq.apps.commtrack.resources.v0_1 import ProductResource
from corehq.apps.locations.resources.v0_1 import LocationResource
from django.conf.urls.defaults import *
from tastypie.api import Api
from dimagi.utils.decorators import inline


API_LIST = (
    ((0, 1), (
        v0_1.CommCareUserResource,
        v0_1.CommCareCaseResource,
        v0_1.XFormInstanceResource,
        LocationResource,
        ProductResource
    )),
    ((0, 2), (
        v0_1.CommCareUserResource,
        v0_2.CommCareCaseResource,
        v0_1.XFormInstanceResource,
        LocationResource,
        ProductResource
    )),
    ((0, 3), (
        v0_1.CommCareUserResource,
        v0_3.CommCareCaseResource,
        v0_1.XFormInstanceResource,
        LocationResource,
        ProductResource
    ))
)

@inline
def api_url_patterns():
    for version, resources in API_LIST:
        api = Api(api_name=r'v%d\.%d' % version)
        for R in resources:
            api.register(R())
        yield (r'^', include(api.urls))

urlpatterns = patterns('',
    *api_url_patterns
)