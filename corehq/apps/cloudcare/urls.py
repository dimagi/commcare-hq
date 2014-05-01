from django.conf.urls.defaults import patterns, url, include
from django.views.generic import TemplateView
from corehq.apps.cloudcare.views import EditCloudcareUserPermissionsView

app_urls = patterns('corehq.apps.cloudcare.views',
    url(r'^view/(?P<app_id>[\w-]+)/modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/context/$',
        'form_context', name='cloudcare_form_context'),
    url(r'^(?P<urlPath>.*)$', 'cloudcare_main', name='cloudcare_main'),
)

cases_urls = patterns('corehq.apps.cloudcare.views',
    url(r'^view/(?P<case_id>[\w-]*)/$', 'view_case', name='cloudcare_view_case'),
    url(r'^create/$', 'view_case', {'case_id': None}, name='cloudcare_create_case'),
)

api_urls = patterns('corehq.apps.cloudcare.views',
    url(r'^groups/(?P<user_id>[\w-]*)/$', 'get_groups', name='cloudcare_get_groups'),
    url(r'^cases/$', 'get_cases', name='cloudcare_get_cases'),
    url(r'^cases/module/(?P<app_id>[\w-]+)/modules-(?P<module_id>[\w-]+)/$', 
        'filter_cases', name='cloudcare_filter_cases'),
    url(r'^apps/$', 'get_apps_api', name='cloudcare_get_apps'),
    url(r'^apps/(?P<app_id>[\w-]*)/$', 'get_app_api', name='cloudcare_get_app'),
    url(r'^fixtures/(?P<user_id>[\w-]*)/$', 'get_fixtures', name='cloudcare_get_fixtures'),
    url(r'^fixtures/(?P<user_id>[\w-]*)/(?P<fixture_id>[:\w-]*)$', 'get_fixtures', 
        name='cloudcare_get_fixtures'),
    url(r'^sessions/$', 'get_sessions', name='cloudcare_get_sessions'),
    url(r'^sessions/(?P<session_id>[\w-]*)/$', 'get_session_context', name='cloudcare_get_session_context'),

    
)

# used in settings urls
settings_urls = patterns('corehq.apps.cloudcare.views',
    url(r'^app/', EditCloudcareUserPermissionsView.as_view(), name=EditCloudcareUserPermissionsView.urlname),
)

urlpatterns = patterns('corehq.apps.cloudcare.views',
    url(r'^$', 'default', name='cloudcare_default'),
    url(r'^apps/', include(app_urls)),
    url(r'^cases/', include(cases_urls)),
    url(r'^test/$', TemplateView.as_view(template_name='cloudcare/test.html')),
    url(r'^api/', include(api_urls)),
)
