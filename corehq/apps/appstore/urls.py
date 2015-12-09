from django.conf.urls import url, patterns

urlpatterns = patterns('corehq.apps.appstore.views',
    url(r'^$', 'appstore', name='appstore'),
    url(r'^api/', 'appstore_api', name='appstore_api'),

    url(r'^(?P<domain>[\w\.-]+)/info/$', 'project_info', name='project_info'),

    url(r'^deployments/$', 'deployments', name='deployments'),
    url(r'^deployments/api/$', 'deployments_api', name='deployments_api'),
    url(r'^deployments/(?P<domain>[\w\.-]+)/info/$', 'deployment_info', name='deployment_info'),

    url(r'^(?P<domain>[\w\.-]+)/approve/$', 'approve_app', name='approve_appstore_app'),
    url(r'^(?P<domain>[\w\.-]+)/copy/$', 'copy_snapshot', name='domain_copy_snapshot'),
    url(r'^(?P<domain>[\w\.-]+)/importapp/$', 'import_app', name='import_app_from_snapshot'),
    url(r'^(?P<domain>[\w\.-]+)/image/$', 'project_image', name='appstore_project_image'),
    url(r'^(?P<domain>[\w\.-]+)/documentation_file/$', 'project_documentation_file',
        name='appstore_project_documentation_file'),
    url(r'^(?P<domain>[\w\.-]+)/multimedia/$', 'media_files', name='media_files'),
)

