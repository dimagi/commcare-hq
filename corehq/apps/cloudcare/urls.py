from django.conf.urls.defaults import patterns, url, include
from django.views.generic.simple import direct_to_template

app_urls = patterns('corehq.apps.cloudcare.views',
    url(r'^$', 'app_list', name='cloudcare_app_list'),
    url(r'^view/(?P<app_id>[\w-]+)/$', 'view_app', name='cloudcare_view_app'),
    url(r'^view/(?P<app_id>[\w-]+)/modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/enter/$',
        'enter_form', name='cloudcare_enter_form'),
    url(r'^view/(?P<app_id>[\w-]+)/modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/complete/$',
        'form_complete', name='cloudcare_form_complete'),
)

cases_urls = patterns('corehq.apps.cloudcare.views',
    url(r'^list/$', 'case_list', name='cloudcare_case_list'),
    url(r'^view/(?P<case_id>[\w-]*)/$', 'view_case', name='cloudcare_view_case'),
    url(r'^create/$', 'view_case', {'case_id': None}, name='cloudcare_create_case'),
)

api_urls = patterns('corehq.apps.cloudcare.views',
    url(r'^groups/(?P<user_id>[\w-]*)/$', 'get_groups', name='cloudcare_get_groups'),
    url(r'^cases/$', 'get_cases', name='cloudcare_get_cases'),
    url(r'^apps/$', 'get_apps_api', name='cloudcare_get_apps'),
    url(r'^apps/(?P<app_id>[\w-]*)/$', 'get_app_api', name='cloudcare_get_app'),
)

urlpatterns = patterns('corehq.apps.cloudcare.views',
    url(r'^apps/', include(app_urls)),
    url(r'^cases/', include(cases_urls)),
    url(r'^test/$', direct_to_template, {'template': 'cloudcare/test.html'}),
    url(r'^api/', include(api_urls)),

)