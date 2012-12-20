from corehq.apps.api.domainapi import DomainAPI
from corehq.apps.api.resources import v0_1, v0_2, v0_3
from corehq.apps.locations.resources.v0_1 import LocationResource
from django.conf.urls.defaults import *
from tastypie.api import Api
from corehq.apps.api.es import XFormES
from dimagi.utils.decorators import inline

API_LIST = (
    ((0, 1), (v0_1.CommCareUserResource, v0_1.CommCareCaseResource, v0_1.XFormInstanceResource, LocationResource)),
    ((0, 2), (v0_1.CommCareUserResource, v0_2.CommCareCaseResource, v0_1.XFormInstanceResource, LocationResource)),
    ((0, 3), (v0_1.CommCareUserResource, v0_3.CommCareCaseResource, v0_1.XFormInstanceResource, LocationResource))
)

@inline
def api_url_patterns():
    for version, resources in API_LIST:
        api = Api(api_name=r'v%d\.%d' % version)
        for R in resources:
            api.register(R())
        yield (r'^', include(api.urls))
    yield url(r'^v0.1/xform_es/$', XFormES.as_view())
    for view_class in DomainAPI.__subclasses__():
        yield url(r'^custom/%s/v%s/$' % (view_class.api_name(), view_class.api_version()), view_class.as_view(), name="%s_%s" % (view_class.api_name(), view_class.api_version()))


urlpatterns = patterns('',
    *api_url_patterns)
