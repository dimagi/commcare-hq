from django.conf.urls.defaults import *

urlpatterns = patterns('corehq.apps.appstore.views',
    url(r'^(?P<domain>[\w\.-]+)/info/$', 'project_info', name='project_info'),
    url(r'^search/$', 'search_snapshots', name='appstore_search_snapshots'),
    url(r'^filter/(?P<filter_by>[\w]+)/(?P<filter>[^/]+)/$', 'filter_snapshots', name='appstore_filter_snapshots'),
    url(r'^filter/(?P<filter_by>[\w]+)/(?P<filter>[^/]+)/(?P<sort_by>[\w_]+)/$', 'filter_snapshots', name='sorted_appstore_filter_snapshots'),

    url(r'^$', 'appstore', name='appstore'),
    url(r'^(?P<sort_by>[\w_]+)/$', 'appstore', name='sorted_appstore'),

    url(r'^async/filters/(?P<slug>[\w_]+)/$', 'report_dispatcher', name="appstore_interface_dispatcher", kwargs={
        'async_filters': True
    }),
    url(r'^async/(?P<slug>[\w_]+)/$', 'report_dispatcher', name="async_report_dispatcher", kwargs={
        'async': True
    }),
    url(r'^store/(?P<slug>[\w_]+)/$', 'report_dispatcher', name="appstore_interface_dispatcher"),
    url(r'^store/advanced$', 'report_dispatcher', name="appstore_interfaces_default", kwargs={
        'slug': 'advanced'
    }),
    url(r'^(?P<domain>[\w\.-]+)/approve/$', 'approve_app', name='approve_appstore_app'),
    url(r'^(?P<domain>[\w\.-]+)/copyapp/', 'copy_snapshot_app', name='copy_snapshot_app'),
    url(r'^(?P<domain>[\w\.-]+)/copy/$', 'copy_snapshot', name='domain_copy_snapshot'),
    url(r'^(?P<domain>[\w\.-]+)/image/$', 'project_image', name='appstore_project_image')
)