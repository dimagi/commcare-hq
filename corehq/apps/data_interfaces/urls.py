from __future__ import absolute_import
from __future__ import unicode_literals
from django.conf.urls import include, url
from corehq.apps.data_interfaces.dispatcher import EditDataInterfaceDispatcher
from corehq.apps.data_interfaces.views import (
    CaseGroupListView,
    CaseGroupCaseManagementView,
    XFormManagementView,
    XFormManagementStatusView,
    AutomaticUpdateRuleListView,
    xform_management_job_poll,
    default,
    AddCaseRuleView,
    EditCaseRuleView,
    find_by_id,
    ExploreCaseDataView,
)
from .interfaces import FormManagementMode


edit_data_urls = [
    url(r'^xform_management/$', XFormManagementView.as_view(), name=XFormManagementView.urlname),
    url(
        r'^xform_management/status/(?P<mode>{archive}|{restore})/(?P<download_id>{id_regex})/$'.format(
            archive=FormManagementMode.ARCHIVE_MODE,
            restore=FormManagementMode.RESTORE_MODE,
            id_regex="(?:dl-)?[0-9a-fA-Z]{25,32}",
        ),
        XFormManagementStatusView.as_view(),
        name=XFormManagementStatusView.urlname
    ),
    url(r'^xform_management/status/poll/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        xform_management_job_poll, name='xform_management_job_poll'),
    url(r'^case_groups/$', CaseGroupListView.as_view(), name=CaseGroupListView.urlname),
    url(r'^case_groups/(?P<group_id>[\w-]+)/$',
        CaseGroupCaseManagementView.as_view(), name=CaseGroupCaseManagementView.urlname),
    url(r'^automatic_updates/$', AutomaticUpdateRuleListView.as_view(),
        name=AutomaticUpdateRuleListView.urlname),
    url(r'^automatic_updates/add/$', AddCaseRuleView.as_view(), name=AddCaseRuleView.urlname),
    url(r'^automatic_updates/edit/(?P<rule_id>\d+)/$', EditCaseRuleView.as_view(), name=EditCaseRuleView.urlname),
    EditDataInterfaceDispatcher.url_pattern(),
]

urlpatterns = [
    url(r'^$', default, name="data_interfaces_default"),
    url(r'^edit/', include(edit_data_urls)),
    url(r'^case_data/', ExploreCaseDataView.as_view(), name=ExploreCaseDataView.urlname),
    url(r'^export/', include('corehq.apps.export.urls')),
    url(r'^find/$', find_by_id, name="data_find_by_id"),
]
