from django.conf.urls import *
from corehq.apps.data_interfaces.dispatcher import DataInterfaceDispatcher, EditDataInterfaceDispatcher
from corehq.apps.data_interfaces.views import CaseGroupListView, CaseGroupCaseManagementView, ArchiveFormView

edit_data_urls = patterns(
    'corehq.apps.data_interfaces.views',
    url(r'^archive_forms/$', ArchiveFormView.as_view(), name=ArchiveFormView.urlname),
    url(r'^case_groups/$', CaseGroupListView.as_view(), name=CaseGroupListView.urlname),
    url(r'^case_groups/(?P<group_id>[\w-]+)/$', CaseGroupCaseManagementView.as_view(), name=CaseGroupCaseManagementView.urlname),
    EditDataInterfaceDispatcher.url_pattern(),
)

urlpatterns = patterns(
    'corehq.apps.data_interfaces.views',
    url(r'^$', "default", name="data_interfaces_default"),
    (r'^edit/', include(edit_data_urls)),
    (r'^export/', include('corehq.apps.export.urls')),
    DataInterfaceDispatcher.url_pattern(),
)


