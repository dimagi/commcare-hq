from django.conf.urls.defaults import *
from corehq.apps.appstore.dispatcher import AppstoreDispatcher

store_urls = patterns('corehq.apps.appstore.views',
    url(r'^$', 'appstore_default', name="appstore_interfaces_default"),
    url(AppstoreDispatcher.pattern(), AppstoreDispatcher.as_view(),
        name=AppstoreDispatcher.name()
    )
)

urlpatterns = patterns('corehq.apps.appstore.views',
    url(r'^$', 'appstore', name='appstore'),
    url(r'^store/', include(store_urls)),

    url(r'^(?P<domain>[\w\.-]+)/info/$', 'project_info', name='project_info'),
    url(r'^search/$', 'search_snapshots', name='appstore_search_snapshots'),
    url(r'^filter/(?P<filter_by>[\w]+)/(?P<filter>[^/]+)/$', 'filter_snapshots', name='appstore_filter_snapshots'),
    url(r'^filter/(?P<filter_by>[\w]+)/(?P<filter>[^/]+)/(?P<sort_by>[\w_]+)/$', 'filter_snapshots', name='sorted_appstore_filter_snapshots'),

    url(r'^(?P<sort_by>[\w_]+)/$', 'appstore', name='sorted_appstore'),

    url(r'^(?P<domain>[\w\.-]+)/approve/$', 'approve_app', name='approve_appstore_app'),
    url(r'^(?P<domain>[\w\.-]+)/copyapp/', 'copy_snapshot_app', name='copy_snapshot_app'),
    url(r'^(?P<domain>[\w\.-]+)/copy/$', 'copy_snapshot', name='domain_copy_snapshot'),
    url(r'^(?P<domain>[\w\.-]+)/image/$', 'project_image', name='appstore_project_image')
)

