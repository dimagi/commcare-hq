from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.appstore.views',
    url(r'^search/$', 'search_snapshots', name='appstore_search_snapshots'),
    url(r'^$', 'appstore', name='appstore'),
    url(r'^/info/(?P<domain>[\w\.-]+)/$', 'app_info', name='app_info'),
)