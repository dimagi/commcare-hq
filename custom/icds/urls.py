from django.conf.urls import url

from custom.icds.location_reassignment.views import (
    LocationReassignmentDownloadOnlyView,
    LocationReassignmentView,
    download_location_reassignment_template,
)
from custom.icds.views.data_pull import CustomDataPull
from custom.icds.views.hosted_ccz import (
    EditHostedCCZLink,
    HostedCCZView,
    ManageHostedCCZ,
    ManageHostedCCZLink,
    ccz_hostings_json,
    download_ccz,
    download_ccz_supporting_files,
    recreate_hosted_ccz,
    remove_hosted_ccz,
)

urlpatterns = [
    url(r'^ccz/hostings/manage', ManageHostedCCZ.as_view(), name=ManageHostedCCZ.urlname),
    url(r'^ccz/hostings/json', ccz_hostings_json, name='ccz_hostings_json'),
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
    url(r'^custom_data_pull/', CustomDataPull.as_view(), name=CustomDataPull.urlname),
    url(r'^location_reassignment_download/$', LocationReassignmentDownloadOnlyView.as_view(),
        name=LocationReassignmentDownloadOnlyView.urlname),
    url(r'^location_reassignment/$', LocationReassignmentView.as_view(),
        name=LocationReassignmentView.urlname),
    url(r'^location_reassignment/download/$', download_location_reassignment_template,
        name='download_location_reassignment_template'),
]
