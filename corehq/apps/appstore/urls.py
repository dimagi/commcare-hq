from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.appstore.views',
    url(r'^info/(?P<domain>[\w\.-]+)/$', 'app_info', name='app_info'),
    url(r'^search/$', 'search_snapshots', name='appstore_search_snapshots'),
    url(r'^filter/(?P<filter_by>[\w]+)/(?P<filter>[+\w-]+)/', 'filter_snapshots', name='appstore_filter_snapshots'),
    url(r'^filter/(?P<filter_by>[\w]+)/', 'filter_choices', name='appstore_filter_choices'),
    url(r'^$', 'appstore', name='appstore'),
#    url(r'^$', "default", name="appstore_interfaces_default"),
    url(r'^async/filters/store/(?P<slug>[\w_]+)/$', 'report_dispatcher', name="appstore_interface_dispatcher", kwargs={
        'async_filters': True
    }),
    url(r'^async/store/(?P<slug>[\w_]+)/$', 'report_dispatcher', name="async_report_dispatcher", kwargs={
        'async': True
    }),
    url(r'^store/(?P<slug>[\w_]+)/$', 'report_dispatcher', name="appstore_interface_dispatcher"),
    url(r'^store/appstore/$', 'report_dispatcher', name="appstore_interfaces_default", kwargs={'slug':'appstore'})

)