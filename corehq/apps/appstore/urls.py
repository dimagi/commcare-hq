from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template
from corehq.apps.appstore.dispatcher import AppstoreDispatcher

store_urls = patterns('corehq.apps.appstore.views',
    url(r'^$', 'appstore_default', name="appstore_interfaces_default"),
    AppstoreDispatcher.url_pattern(),
)

urlpatterns = patterns('corehq.apps.appstore.views',
    url(r'^$', 'appstore', name='appstore'),
    url(r'^api/', 'appstore_api', name='appstore_api'),
    url(r'^store/', include(store_urls)),

    url(r'^(?P<domain>[\w\.-]+)/info/$', 'project_info', name='project_info'),

    url(r'^deployments/$', 'deployments', name='deployments'),
    url(r'^deployments/api/$', 'deployments_api', name='deployments_api'),
    url(r'^deployments/(?P<domain>[\w\.-]+)/info/$', 'deployment_info', name='deployment_info'),

    url(r'^(?P<domain>[\w\.-]+)/approve/$', 'approve_app', name='approve_appstore_app'),
    url(r'^(?P<domain>[\w\.-]+)/copy/$', 'copy_snapshot', name='domain_copy_snapshot'),
    url(r'^(?P<domain>[\w\.-]+)/importapp/$', 'import_app', name='import_app_from_snapshot'),
    url(r'^(?P<domain>[\w\.-]+)/image/$', 'project_image', name='appstore_project_image'),
    url(r'^(?P<domain>[\w\.-]+)/multimedia/$', 'media_files', name='media_files'),

    url(r'^cda/$', direct_to_template, {'template': 'cda.html'}, name='cda'),
)

