from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.data_interfaces.views',
    url(r'^$', "default", name="data_interfaces_default"),
    url(r'^async/filters/(?P<slug>[\w_]+)/$', 'report_dispatcher', name="data_interface_dispatcher", kwargs={
        'async_filters': True
    }),
    url(r'^async/(?P<slug>[\w_]+)/$', 'report_dispatcher', name="async_report_dispatcher", kwargs={
        'async': True
    }),
    url(r'^(?P<slug>[\w_]+)/$', 'report_dispatcher', name="data_interface_dispatcher"),
)