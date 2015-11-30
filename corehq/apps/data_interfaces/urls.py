from django.conf.urls import *
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher, EditDataInterfaceDispatcher
from corehq.apps.data_interfaces.views import (CaseGroupListView,
                                               CaseGroupCaseManagementView,
                                               ArchiveFormView,
                                               XFormManagementView,
                                               XFormManagementStatusView,
                                               AutomaticUpdateRuleListView,
                                               AddAutomaticUpdateRuleView,
                                               EditAutomaticUpdateRuleView)
from .interfaces import FormManagementMode



edit_data_urls = patterns(
    'corehq.apps.data_interfaces.views',
    url(r'^archive_forms/$', ArchiveFormView.as_view(), name=ArchiveFormView.urlname),
    url(r'^xform_management/$', XFormManagementView.as_view(), name=XFormManagementView.urlname),
    url(
        r'^xform_management/status/(?P<mode>{archive}|{restore})/(?P<download_id>{id_regex})/$'.format(
            archive=FormManagementMode.ARCHIVE_MODE,
            restore=FormManagementMode.RESTORE_MODE,
            id_regex="[0-9a-fA-Z]{25,32}",
        ),
        XFormManagementStatusView.as_view(),
        name=XFormManagementStatusView.urlname
    ),
    url(r'^xform_management/status/poll/(?P<download_id>[0-9a-fA-Z]{25,32})/$',
        'xform_management_job_poll', name='xform_management_job_poll'),
    url(r'^case_groups/$', CaseGroupListView.as_view(), name=CaseGroupListView.urlname),
    url(r'^case_groups/(?P<group_id>[\w-]+)/$',
        CaseGroupCaseManagementView.as_view(), name=CaseGroupCaseManagementView.urlname),
    url(r'^automatic_updates/$', AutomaticUpdateRuleListView.as_view(),
        name=AutomaticUpdateRuleListView.urlname),
    url(r'^automatic_updates/add/$', AddAutomaticUpdateRuleView.as_view(),
        name=AddAutomaticUpdateRuleView.urlname),
    url(r'^automatic_updates/edit/(?P<rule_id>\d+)/$', EditAutomaticUpdateRuleView.as_view(),
        name=EditAutomaticUpdateRuleView.urlname),
    EditDataInterfaceDispatcher.url_pattern(),
)

urlpatterns = patterns(
    'corehq.apps.data_interfaces.views',
    url(r'^$', "default", name="data_interfaces_default"),
    (r'^edit/', include(edit_data_urls)),
    (r'^export/', include('corehq.apps.export.urls')),
)
