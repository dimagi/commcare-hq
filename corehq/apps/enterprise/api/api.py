from tastypie.api import Api

from corehq.apps.enterprise.api.resources import (
    DomainResource,
    FormSubmissionResource,
    MobileUserResource,
    ODataFeedResource,
    WebUserResource,
    SMSResource,
)

v1_api = Api(api_name='v1')
v1_api.register(DomainResource())
v1_api.register(WebUserResource())
v1_api.register(MobileUserResource())
v1_api.register(FormSubmissionResource())
v1_api.register(ODataFeedResource())
v1_api.register(SMSResource())
