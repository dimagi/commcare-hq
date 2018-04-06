from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import url, include

from corehq.apps.cloudcare.views import (
    EditCloudcareUserPermissionsView,
    ReadableQuestions,
    FormplayerMain,
    FormplayerMainPreview,
    FormplayerPreviewSingleApp,
    PreviewAppView,
    LoginAsUsers,
    SingleAppLandingPageView,
    form_context, get_cases,
    get_fixtures, default,
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
]

api_urls = [
    url(r'^login_as/users/$', LoginAsUsers.as_view(), name=LoginAsUsers.urlname),
    url(r'^cases/$', get_cases, name='cloudcare_get_cases'),
    url(r'^fixtures/(?P<user_id>[\w-]+)/(?P<fixture_id>[:\w-]+)$', get_fixtures,
        name='cloudcare_get_fixtures'),
    url(r'^readable_questions/$', ReadableQuestions.as_view(), name=ReadableQuestions.urlname),
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
