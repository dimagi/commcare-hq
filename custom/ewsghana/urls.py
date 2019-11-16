from django.conf.urls import url, include
from corehq.apps.api.urls import CommCareHqApi
from custom.ewsghana.resources.v0_1 import EWSLocationResource
from custom.ewsghana.views import (
    configure_in_charge,
)

hq_api = CommCareHqApi(api_name='v0.3')
hq_api.register(EWSLocationResource())

urlpatterns = [
    url(r'^configure_in_charge/$', configure_in_charge, name='configure_in_charge'),
    url(r'^', include(hq_api.urls)),
]
