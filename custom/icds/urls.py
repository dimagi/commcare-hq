from __future__ import absolute_import
from __future__ import unicode_literals

from django.conf.urls import url
from custom.icds.views.ccz_hosting import (
    ManageCCZHosting,
    ManageCCZHostingLink,
    EditCCZHostingLink,
    CCZHostingView,
    remove_ccz_hosting,
    download_ccz,
    download_ccz_supporting_files,
)

urlpatterns = [
    url(r'^ccz/hostings/manage', ManageCCZHosting.as_view(), name=ManageCCZHosting.urlname),
    url(r'^ccz/hostings/links', ManageCCZHostingLink.as_view(), name=ManageCCZHostingLink.urlname),
    url(r'^ccz/hostings/link/(?P<link_id>[\d-]+)/edit/', EditCCZHostingLink.as_view(),
        name=EditCCZHostingLink.urlname),
    url(r'^ccz/hostings/link/(?P<hosting_id>[\d-]+)/delete/', remove_ccz_hosting,
        name="remove_ccz_hosting"),
    url(r'^ccz/hostings/(?P<hosting_id>[\w-]+)/download/(?P<blob_id>[\w-]+)/', download_ccz,
        name="ccz_hosting_download_ccz"),
    url(r'^ccz/hostings/download/support/(?P<hosting_supporting_file_id>[\w-]+)/', download_ccz_supporting_files,
        name="ccz_hosting_download_supporting_files"),
    url(r'^ccz/hostings/link/(?P<link_id>[\d-]+)/', ManageCCZHostingLink.as_view(),
        name=ManageCCZHostingLink.urlname),
    url(r'^ccz/hostings/(?P<identifier>[\w-]+)/', CCZHostingView.as_view(), name=CCZHostingView.urlname),
]
