from __future__ import absolute_import
from __future__ import unicode_literals

from django.conf.urls import url
from custom.icds.views.hosted_ccz import (
    ManageHostedCCZ,
    ManageHostedCCZLink,
    EditHostedCCZLink,
    HostedCCZView,
    remove_hosted_ccz,
    recreate_hosted_ccz,
    download_ccz,
    download_ccz_supporting_files,
)

urlpatterns = [
    url(r'^ccz/hostings/manage', ManageHostedCCZ.as_view(), name=ManageHostedCCZ.urlname),
    url(r'^ccz/hostings/links', ManageHostedCCZLink.as_view(), name=ManageHostedCCZLink.urlname),
    url(r'^ccz/hostings/link/(?P<link_id>[\d-]+)/edit/', EditHostedCCZLink.as_view(),
        name=EditHostedCCZLink.urlname),
    url(r'^ccz/hostings/link/(?P<hosting_id>[\d-]+)/delete/', remove_hosted_ccz,
        name="remove_hosted_ccz"),
    url(r'^ccz/hostings/link/(?P<hosting_id>[\d-]+)/recreate/', recreate_hosted_ccz,
        name="recreate_hosted_ccz"),
    url(r'^ccz/hostings/(?P<hosting_id>[\w-]+)/download/', download_ccz,
        name="hosted_ccz_download_ccz"),
    url(r'^ccz/hostings/download/support/(?P<hosting_supporting_file_id>[\w-]+)/', download_ccz_supporting_files,
        name="hosted_ccz_download_supporting_files"),
    url(r'^ccz/hostings/link/(?P<link_id>[\d-]+)/', ManageHostedCCZLink.as_view(),
        name=ManageHostedCCZLink.urlname),
    url(r'^ccz/hostings/(?P<identifier>[\w-]+)/', HostedCCZView.as_view(), name=HostedCCZView.urlname),
]
