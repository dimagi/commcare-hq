from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.appstore.views',
    url(r'^search/$', 'search_snapshots', name='appstore_search_snapshots'),
    url(r'^(?P<filter_by>[\w]+)/(?P<filter>[+\w-]+)/', 'filter_snapshots', name='appstore_filter_snapshots'),
    url(r'^(?P<filter_by>[\w]+)/', 'filter_choices', name='appstore_filter_choices'),
    url(r'^$', 'appstore', name='appstore'),
    url(r'^info/(?P<domain>[\w\.-]+)/$', 'app_info', name='app_info'),
)