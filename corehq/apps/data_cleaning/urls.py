from django.urls import re_path as url

from corehq.apps.data_cleaning.views.summary import ChangesSummaryView
from corehq.apps.data_cleaning.views.bulk_edit import (
    EditSelectedRecordsFormView,
)
from corehq.apps.data_cleaning.views.columns import (
    ManageColumnsFormView,
)
from corehq.apps.data_cleaning.views.filters import (
    ManagePinnedFiltersView,
    ManageFiltersView,
)
from corehq.apps.data_cleaning.views.main import (
    BulkEditCasesMainView,
    BulkEditCasesSessionView,
    clear_session_caches,
    download_form_ids,
)
from corehq.apps.data_cleaning.views.tables import (
    EditCasesTableView,
    RecentCaseSessionsTableView,
)
from corehq.apps.data_cleaning.views.start import (
    StartCaseSessionView,
)
from corehq.apps.data_cleaning.views.status import (
    BulkEditSessionStatusView,
)

urlpatterns = [
    url(r'^cases/$', BulkEditCasesMainView.as_view(), name=BulkEditCasesMainView.urlname),
    url(r'^start/case/$', StartCaseSessionView.as_view(), name=StartCaseSessionView.urlname),
    url(r'^tasks/case/$', RecentCaseSessionsTableView.as_view(), name=RecentCaseSessionsTableView.urlname),
    url(r'^cases/(?P<session_id>[\w\-]+)/$', BulkEditCasesSessionView.as_view(),
        name=BulkEditCasesSessionView.urlname),
    url(r'^cases/(?P<session_id>[\w\-]+)/table/$', EditCasesTableView.as_view(),
        name=EditCasesTableView.urlname),
    url(r'^cases/(?P<session_id>[\w\-]+)/summary/$', ChangesSummaryView.as_view(),
        name=ChangesSummaryView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/status/$', BulkEditSessionStatusView.as_view(),
        name=BulkEditSessionStatusView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/filters/$', ManageFiltersView.as_view(),
        name=ManageFiltersView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/filters/pinned/$', ManagePinnedFiltersView.as_view(),
        name=ManagePinnedFiltersView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/columns/$', ManageColumnsFormView.as_view(),
        name=ManageColumnsFormView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/clean/$', EditSelectedRecordsFormView.as_view(),
        name=EditSelectedRecordsFormView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/clear/$', clear_session_caches,
        name="bulk_edit_clear_session_caches"),
    url(r'^form_ids/(?P<session_id>[\w\-]+)/$', download_form_ids, name='download_form_ids'),
]
