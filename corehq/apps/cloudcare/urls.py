from django.conf.urls import patterns, url, include

from corehq.apps.cloudcare.views import (
    EditCloudcareUserPermissionsView,
    CloudcareMain,
    ReadableQuestions,
    form_context, get_cases, filter_cases, get_apps_api, get_app_api,
    get_fixtures, get_sessions, get_session_context, get_ledgers, render_form,
    sync_db_api, default,
)

app_urls = patterns('corehq.apps.cloudcare.views',
    url(r'^view/(?P<app_id>[\w-]+)/modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/context/$',
        form_context, name='cloudcare_form_context'),
    url(r'^(?P<urlPath>.*)$', CloudcareMain.as_view(), name='cloudcare_main'),
)

api_urls = patterns('corehq.apps.cloudcare.views',
    url(r'^cases/$', get_cases, name='cloudcare_get_cases'),
    url(r'^cases/module/(?P<app_id>[\w-]+)/modules-(?P<module_id>[\w-]+)/$', 
        filter_cases, name='cloudcare_filter_cases'),
    url(r'^cases/module/(?P<app_id>[\w-]+)/modules-(?P<module_id>[\w-]+)/parent/(?P<parent_id>[\w-]+)/$',
        filter_cases, name='cloudcare_filter_cases_with_parent'),
    url(r'^apps/$', get_apps_api, name='cloudcare_get_apps'),
    url(r'^apps/(?P<app_id>[\w-]*)/$', get_app_api, name='cloudcare_get_app'),
    url(r'^fixtures/(?P<user_id>[\w-]*)/$', get_fixtures, name='cloudcare_get_fixtures'),
    url(r'^fixtures/(?P<user_id>[\w-]*)/(?P<fixture_id>[:\w-]*)$', get_fixtures,
        name='cloudcare_get_fixtures'),
    url(r'^sessions/$', get_sessions, name='cloudcare_get_sessions'),
    url(r'^sessions/(?P<session_id>[\w-]*)/$', get_session_context, name='cloudcare_get_session_context'),
    url(r'^ledgers/$', get_ledgers, name='cloudcare_get_ledgers'),
    url(r'^render_form/$', render_form, name='cloudcare_render_form'),
    url(r'^readable_questions/$', ReadableQuestions.as_view(), name=ReadableQuestions.urlname),
    url(r'^sync_db/$', sync_db_api, name='cloudcare_sync_db'),
)

# used in settings urls
settings_urls = patterns('corehq.apps.cloudcare.views',
    url(r'^app/', EditCloudcareUserPermissionsView.as_view(), name=EditCloudcareUserPermissionsView.urlname),
)

urlpatterns = patterns('corehq.apps.cloudcare.views',
    url(r'^$', default, name='cloudcare_default'),
    url(r'^apps/', include(app_urls)),
    url(r'^api/', include(api_urls)),
)
