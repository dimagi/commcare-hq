from corehq.apps.api.resources import v0_1, v0_2, v0_3
from django.conf.urls.defaults import *
from tastypie.api import Api
from corehq.apps.api.xform_es import XFormES
from dimagi.utils.decorators import inline

API_LIST = (
    ((0, 1), (v0_1.CommCareUserResource, v0_1.CommCareCaseResource, v0_1.XFormInstanceResource)),
    ((0, 2), (v0_1.CommCareUserResource, v0_2.CommCareCaseResource, v0_1.XFormInstanceResource)),
    ((0, 3), (v0_1.CommCareUserResource, v0_3.CommCareCaseResource, v0_1.XFormInstanceResource))
)

@inline
def api_url_patterns():
    for version, resources in API_LIST:
        api = Api(api_name=r'v%d\.%d' % version)
        for R in resources:
            api.register(R())
        yield (r'^', include(api.urls))
    yield url(r'^v0.1/xform_es/$', XFormES.as_view())

urlpatterns = patterns('',
    *api_url_patterns)