from django.conf.urls import url, include

from corehq.apps.cloudcare.views import (
    EditCloudcareUserPermissionsView,
    CloudcareMain,
    ReadableQuestions,
    FormplayerMain,
    FormplayerMainPreview,
    FormplayerPreviewSingleApp,
    PreviewAppView,
    LoginAsUsers,
    SingleAppLandingPageView,
    form_context, get_cases, filter_cases, get_apps_api, get_app_api,
    get_fixtures, get_sessions, get_session_context, get_ledgers, render_form,
    sync_db_api, default,
)

app_urls = [
    url(r'^view/(?P<app_id>[\w-]+)/modules-(?P<module_id>[\w-]+)/forms-(?P<form_id>[\w-]+)/context/$',
        form_context, name='cloudcare_form_context'),
    url(r'^v2/$', FormplayerMain.as_view(), name=FormplayerMain.urlname),
    url(r'^v2/preview/$', FormplayerMainPreview.as_view(), name=FormplayerMainPreview.urlname),
    url(
        r'^v2/preview/(?P<app_id>[\w-]+)/$',
        FormplayerPreviewSingleApp.as_view(),
        name=FormplayerPreviewSingleApp.urlname,
    ),
    url(r'^preview_app/(?P<app_id>[\w-]+)/$', PreviewAppView.as_view(), name=PreviewAppView.urlname),
    url(
        r'^home/(?P<app_hash>[\w-]+)/$',
        SingleAppLandingPageView.as_view(),
        name=SingleAppLandingPageView.urlname
    ),
    url(r'^(?P<urlPath>.*)$', CloudcareMain.as_view(), name='cloudcare_main'),
]

api_urls = [
    url(r'^login_as/users/$', LoginAsUsers.as_view(), name=LoginAsUsers.urlname),
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
]

# used in settings urls
settings_urls = [
    url(r'^app/', EditCloudcareUserPermissionsView.as_view(), name=EditCloudcareUserPermissionsView.urlname),
]

urlpatterns = [
    url(r'^$', default, name='cloudcare_default'),
    url(r'^apps/', include(app_urls)),
    url(r'^api/', include(api_urls)),
]
