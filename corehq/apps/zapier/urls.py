from django.urls import include, re_path as url

from corehq.apps.api.urls import CommCareHqApi
from corehq.apps.zapier.api.v0_5 import (
    ZapierApplicationResource,
    ZapierCustomActionFieldCaseResource,
    ZapierCustomFieldCaseResource,
    ZapierCustomTriggerFieldFormResource,
    ZapierXFormInstanceResource,
)
from corehq.apps.zapier.views import SubscribeView, UnsubscribeView

hq_api = CommCareHqApi(api_name='v0.5')
hq_api.register(ZapierXFormInstanceResource())
hq_api.register(ZapierCustomTriggerFieldFormResource())
hq_api.register(ZapierCustomActionFieldCaseResource())
hq_api.register(ZapierCustomFieldCaseResource())
hq_api.register(ZapierApplicationResource())

urlpatterns = [
    url(r'^subscribe/$', SubscribeView.as_view(), name=SubscribeView.urlname),
    url(r'^unsubscribe/$', UnsubscribeView.as_view(), name=UnsubscribeView.urlname),
    url(r'^api/', include(hq_api.urls)),
]
