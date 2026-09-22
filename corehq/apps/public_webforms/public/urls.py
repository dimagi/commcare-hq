from django.urls import re_path as url

from corehq.apps.public_webforms.public.views import (
    PublicFormView,
    PublicWebformLinkSentView,
    PublicWebformRequestView,
    PublicFormSubmittedView,
)

urlpatterns = [
    url(
        r'^(?P<public_id>[a-f0-9]{32})/$',
        PublicWebformRequestView.as_view(),
        name=PublicWebformRequestView.urlname,
    ),
    url(
        r'^(?P<public_id>[a-f0-9]{32})/sent/$',
        PublicWebformLinkSentView.as_view(),
        name=PublicWebformLinkSentView.urlname,
    ),
    url(
        r'^(?P<public_id>[a-f0-9]{32})/submitted/$',
        PublicFormSubmittedView.as_view(),
        name=PublicFormSubmittedView.urlname,
    ),
    url(
        r'^(?P<public_id>[a-f0-9]{32})/(?P<session_id>[a-f0-9]{32})/$',
        PublicFormView.as_view(),
        name=PublicFormView.urlname,
    ),
]
