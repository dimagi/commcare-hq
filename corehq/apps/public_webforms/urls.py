from django.urls import re_path as url

from corehq.apps.public_webforms.views import (
    CreatePublicWebformView,
    ManagePublicWebformsView,
    PublicWebformTableView,
    public_webform_qr_code,
)

urlpatterns = [
    url(r'^$', ManagePublicWebformsView.as_view(), name=ManagePublicWebformsView.urlname),
    url(r'^create/$', CreatePublicWebformView.as_view(), name=CreatePublicWebformView.urlname),
    url(r'^table/$', PublicWebformTableView.as_view(), name=PublicWebformTableView.urlname),
    url(r'^(?P<webform_id>\d+)/qr_code/$', public_webform_qr_code,
        name='public_webform_qr_code'),
]
