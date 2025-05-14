from django.urls import re_path as url

from corehq.apps.data_cleaning.views.summary import ChangesSummaryView
from corehq.apps.data_cleaning.views.cleaning import (
    CleanSelectedRecordsFormView,
)
from corehq.apps.data_cleaning.views.columns import (
    ManageColumnsFormView,
)
from corehq.apps.data_cleaning.views.filters import (
    PinnedFilterFormView,
    ManageFiltersFormView,
)
from corehq.apps.data_cleaning.views.main import (
    BulkEditCasesMainView,
    CleanCasesSessionView,
    clear_session_caches,
    download_form_ids,
)
from corehq.apps.data_cleaning.views.tables import (
    CleanCasesTableView,
    RecentCaseSessionsTableView,
)
from corehq.apps.data_cleaning.views.start import (
    StartCaseSessionView,
)

urlpatterns = [
    url(r'^cases/$', BulkEditCasesMainView.as_view(), name=BulkEditCasesMainView.urlname),
    url(r'^start/case/$', StartCaseSessionView.as_view(), name=StartCaseSessionView.urlname),
    url(r'^tasks/case/$', RecentCaseSessionsTableView.as_view(), name=RecentCaseSessionsTableView.urlname),
    url(r'^cases/(?P<session_id>[\w\-]+)/$', CleanCasesSessionView.as_view(),
        name=CleanCasesSessionView.urlname),
    url(r'^cases/(?P<session_id>[\w\-]+)/table/$', CleanCasesTableView.as_view(),
        name=CleanCasesTableView.urlname),
    url(r'^cases/(?P<session_id>[\w\-]+)/summary/$', ChangesSummaryView.as_view(),
        name=ChangesSummaryView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/filters/$', ManageFiltersFormView.as_view(),
        name=ManageFiltersFormView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/filters/pinned/$', PinnedFilterFormView.as_view(),
        name=PinnedFilterFormView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/columns/$', ManageColumnsFormView.as_view(),
        name=ManageColumnsFormView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/clean/$', CleanSelectedRecordsFormView.as_view(),
        name=CleanSelectedRecordsFormView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/clear/$', clear_session_caches,
        name="data_cleaning_clear_session_caches"),
    url(r'^form_ids/(?P<session_id>[\w\-]+)/$', download_form_ids, name='download_form_ids'),
]
