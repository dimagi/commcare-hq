from django.urls import re_path as url

from corehq.apps.public_webforms.public.views import (
    PublicWebformLinkSentView,
    PublicWebformRequestView,
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
]
