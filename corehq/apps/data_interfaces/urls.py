from django.conf.urls.defaults import *
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher

urlpatterns = patterns('corehq.apps.data_interfaces.views',
    url(r'^$', "default", name="data_interfaces_default"),
    DataInterfaceDispatcher.url_pattern(),
)