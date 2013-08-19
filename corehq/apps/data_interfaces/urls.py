from django.conf.urls.defaults import *
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher, EditDataInterfaceDispatcher

edit_data_urls = patterns(
    'corehq.apps.data_interfaces.views',
    EditDataInterfaceDispatcher.url_pattern(),
)

urlpatterns = patterns(
    'corehq.apps.data_interfaces.views',
    url(r'^$', "default", name="data_interfaces_default"),
    (r'^edit/', include(edit_data_urls)),
    (r'^export/', include('corehq.apps.export.urls')),
    DataInterfaceDispatcher.url_pattern(),
)


