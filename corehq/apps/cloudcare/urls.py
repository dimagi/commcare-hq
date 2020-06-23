from django.conf.urls import include, url

from corehq.apps.cloudcare.views import (
    EditCloudcareUserPermissionsView,
    FormplayerMain,
    FormplayerMainPreview,
    FormplayerPreviewSingleApp,
    LoginAsUsers,
    PreviewAppView,
    ReadableQuestions,
    default,
    form_context,
    report_formplayer_error,
)
from corehq.apps.hqwebapp.decorators import waf_allow

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
    url(r'^report_formplayer_error', report_formplayer_error, name='report_formplayer_error')
]

api_urls = [
    url(r'^login_as/users/$', LoginAsUsers.as_view(), name=LoginAsUsers.urlname),
    url(r'^readable_questions/$', waf_allow('XSS_BODY')(ReadableQuestions.as_view()), name=ReadableQuestions.urlname),
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


# This isn't strictly the appropriate place to put this,
# but we don't have similar functionality in formplayer, so it's easier for the time being

waf_allow('XSS_BODY', hard_code_pattern=r'^/formplayer/validate_form$')
waf_allow('XSS_BODY', hard_code_pattern=r'^/formplayer/new-form$')
