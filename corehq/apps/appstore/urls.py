from django.conf.urls import url, patterns
from corehq.apps.appstore.views import (
    CommCareExchangeHomeView,
    ProjectInformationView,
)

urlpatterns = patterns('corehq.apps.appstore.views',
    url(r'^$', CommCareExchangeHomeView.as_view(), name=CommCareExchangeHomeView.urlname),
    url(r'^api/', 'appstore_api', name='appstore_api'),

    url(r'^(?P<snapshot>[\w\.-]+)/info/$', ProjectInformationView.as_view(),
        name=ProjectInformationView.urlname),

    url(r'^deployments/$', 'deployments', name='deployments'),
    url(r'^deployments/api/$', 'deployments_api', name='deployments_api'),
    url(r'^deployments/(?P<snapshot>[\w\.-]+)/info/$', 'deployment_info', name='deployment_info'),

    url(r'^(?P<snapshot>[\w\.-]+)/approve/$', 'approve_app', name='approve_appstore_app'),
    url(r'^(?P<snapshot>[\w\.-]+)/copy/$', 'copy_snapshot', name='domain_copy_snapshot'),
    url(r'^(?P<snapshot>[\w\.-]+)/importapp/$', 'import_app', name='import_app_from_snapshot'),
    url(r'^(?P<snapshot>[\w\.-]+)/image/$', 'project_image', name='appstore_project_image'),
    url(r'^(?P<snapshot>[\w\.-]+)/documentation_file/$', 'project_documentation_file',
        name='appstore_project_documentation_file'),
    url(r'^(?P<snapshot>[\w\.-]+)/multimedia/$', 'media_files', name='media_files'),
)

