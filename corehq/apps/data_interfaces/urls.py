from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.data_interfaces.views',
    url(r'^$', "default", name="data_interfaces_default"),
    url(r'^(?P<slug>[\w_]+)/$', 'report_dispatcher', name="data_interface_dispatcher"),
)