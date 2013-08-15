from django.conf.urls.defaults import *
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher, EditDataInterfaceDispatcher

urlpatterns = patterns('corehq.apps.data_interfaces.views',
    url(r'^$', "default", name="data_interfaces_default"),
    DataInterfaceDispatcher.url_pattern(),
    EditDataInterfaceDispatcher.url_pattern(),
)
