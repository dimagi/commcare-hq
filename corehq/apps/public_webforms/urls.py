from django.urls import re_path as url

from corehq.apps.public_webforms.views import (
    CreatePublicWebformView,
    ManagePublicWebformsView,
    PublicWebformTableView,
)

urlpatterns = [
    url(r'^$', ManagePublicWebformsView.as_view(), name=ManagePublicWebformsView.urlname),
    url(r'^create/$', CreatePublicWebformView.as_view(), name=CreatePublicWebformView.urlname),
    url(r'^table/$', PublicWebformTableView.as_view(), name=PublicWebformTableView.urlname),
]
