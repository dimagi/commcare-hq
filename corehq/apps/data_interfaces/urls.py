from django.conf.urls import include, re_path as url

from corehq.apps.data_interfaces.dispatcher import (
    EditDataInterfaceDispatcher,
    BulkEditDataInterfaceDispatcher,
)
from corehq.apps.data_interfaces.views import (
    AddCaseRuleView,
    AutomaticUpdateRuleListView,
    CaseGroupCaseManagementView,
    CaseGroupListView,
    DeduplicationRuleCreateView,
    DeduplicationRuleEditView,
    DeduplicationRuleListView,
    EditCaseRuleView,
    ViewCaseRuleView,
    ExploreCaseDataView,
    XFormManagementStatusView,
    XFormManagementView,
    default,
    find_by_id,
    xform_management_job_poll,
    BulkCaseActionSatusView,
    case_action_job_poll
)
from corehq.apps.userreports.views import UCRExpressionListView, UCRExpressionEditView

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
    url(r'^case_action/status/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        BulkCaseActionSatusView.as_view(), name=BulkCaseActionSatusView.urlname),
    url(r'^case_action/status/poll/(?P<download_id>(?:dl-)?[0-9a-fA-Z]{25,32})/$',
        case_action_job_poll, name='case_action_job_poll'),
    url(r'^case_groups/$', CaseGroupListView.as_view(), name=CaseGroupListView.urlname),
    url(r'^case_groups/(?P<group_id>[\w-]+)/$',
        CaseGroupCaseManagementView.as_view(), name=CaseGroupCaseManagementView.urlname),
    url(r'^automatic_updates/$', AutomaticUpdateRuleListView.as_view(),
        name=AutomaticUpdateRuleListView.urlname),
    url(r'^automatic_updates/add/$', AddCaseRuleView.as_view(), name=AddCaseRuleView.urlname),
    url(r'^automatic_updates/view/(?P<rule_id>\d+)/$', ViewCaseRuleView.as_view(), name=ViewCaseRuleView.urlname),
    url(r'^automatic_updates/edit/(?P<rule_id>\d+)/$', EditCaseRuleView.as_view(), name=EditCaseRuleView.urlname),
    url(r'^deduplication_rules/$', DeduplicationRuleListView.as_view(), name=DeduplicationRuleListView.urlname),
    url(r'^deduplication_rules/add/$', DeduplicationRuleCreateView.as_view(),
        name=DeduplicationRuleCreateView.urlname),
    url(r'^deduplication_rules/edit/(?P<rule_id>\d+)/$', DeduplicationRuleEditView.as_view(),
        name=DeduplicationRuleEditView.urlname),
    EditDataInterfaceDispatcher.url_pattern(),
    BulkEditDataInterfaceDispatcher.url_pattern(),
]

urlpatterns = [
    url(r'^$', default, name="data_interfaces_default"),
    url(r'^edit/', include(edit_data_urls)),
    url(r'^case_data/', ExploreCaseDataView.as_view(), name=ExploreCaseDataView.urlname),
    url(r'^export/', include('corehq.apps.export.urls')),
    url(r'^find/$', find_by_id, name="data_find_by_id"),
    url(r'^ucr_expressions/$', UCRExpressionListView.as_view(), name=UCRExpressionListView.urlname),
    url(r'^ucr_expressions/(?P<expression_id>[\d-]+)/$', UCRExpressionEditView.as_view(),
        name=UCRExpressionEditView.urlname),
]
