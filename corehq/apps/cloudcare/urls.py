from django.conf.urls import include, re_path as url

from corehq.apps.cloudcare.views import (
    EditCloudcareUserPermissionsView,
    FormplayerMain,
    FormplayerMainPreview,
    FormplayerPreviewSingleApp,
    LoginAsUsers,
    PreviewAppView,
    ReadableQuestions,
    BlockWebAppsView,
    default,
    report_formplayer_error,
    report_sentry_error, api_histogram_metrics
)
from corehq.apps.hqwebapp.decorators import use_bootstrap5, waf_allow

app_urls = [
    url(r'^v2/$', FormplayerMain.as_view(), name=FormplayerMain.urlname),
    url(r'^v2/preview/$', FormplayerMainPreview.as_view(), name=FormplayerMainPreview.urlname),
    url(
        r'^v2/preview/(?P<app_id>[\w-]+)/$',
        FormplayerPreviewSingleApp.as_view(),
        name=FormplayerPreviewSingleApp.urlname,
    ),
    url(r'^preview_app/(?P<app_id>[\w-]+)/$', PreviewAppView.as_view(), name=PreviewAppView.urlname),
    url(r'^report_formplayer_error', report_formplayer_error, name='report_formplayer_error'),
    url(r'^report_sentry_error', report_sentry_error, name='report_sentry_error'),
    url(r'^block_web_apps/$', use_bootstrap5(BlockWebAppsView.as_view()), name=BlockWebAppsView.urlname),
]

api_urls = [
    url(r'^login_as/users/$', LoginAsUsers.as_view(), name=LoginAsUsers.urlname),
    url(r'^readable_questions/$',
        waf_allow('XSS_BODY')(ReadableQuestions.as_view()),
        name=ReadableQuestions.urlname),
]

# used in settings urls
settings_urls = [
    url(r'^app/', EditCloudcareUserPermissionsView.as_view(), name=EditCloudcareUserPermissionsView.urlname),
]

metrics_urls = [
    url(r'^record_api_metrics', api_histogram_metrics, name="api_histogram_metrics")
]

urlpatterns = [
    url(r'^$', default, name='cloudcare_default'),
    url(r'^apps/', include(app_urls)),
    url(r'^api/', include(api_urls)),
    url(r'^metrics/', include(metrics_urls)),
]


# This isn't strictly the appropriate place to put this,
# but we don't have similar functionality in formplayer, so it's easier for the time being

waf_allow('XSS_BODY', hard_code_pattern=r'^/formplayer/validate_form$')
waf_allow('XSS_BODY', hard_code_pattern=r'^/formplayer/new-form$')
waf_allow('XSS_BODY', hard_code_pattern=r'^/formplayer/answer_media$')
