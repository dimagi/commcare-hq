from django.urls import re_path as url

from corehq.apps.data_cleaning.views.columns import (
    ManageColumnsFormView,
)
from corehq.apps.data_cleaning.views.filters import (
    PinnedFilterFormView,
    ManageFiltersFormView,
)
from corehq.apps.data_cleaning.views.main import (
    CleanCasesMainView,
    CleanCasesSessionView,
    clear_session_caches,
    download_form_ids,
    save_case_session,
)
from corehq.apps.data_cleaning.views.tables import (
    CleanCasesTableView,
    CaseCleaningTasksTableView,
)
from corehq.apps.data_cleaning.views.setup import (
    SetupCaseSessionFormView,
)

urlpatterns = [
    url(r'^cases/$', CleanCasesMainView.as_view(), name=CleanCasesMainView.urlname),
    url(r'^setup/case/$', SetupCaseSessionFormView.as_view(), name=SetupCaseSessionFormView.urlname),
    url(r'^tasks/case/$', CaseCleaningTasksTableView.as_view(), name=CaseCleaningTasksTableView.urlname),
    url(r'^cases/(?P<session_id>[\w\-]+)/$', CleanCasesSessionView.as_view(),
        name=CleanCasesSessionView.urlname),
    url(r'^cases/(?P<session_id>[\w\-]+)/table/$', CleanCasesTableView.as_view(),
        name=CleanCasesTableView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/filters/$', ManageFiltersFormView.as_view(),
        name=ManageFiltersFormView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/filters/pinned/$', PinnedFilterFormView.as_view(),
        name=PinnedFilterFormView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/columns/$', ManageColumnsFormView.as_view(),
        name=ManageColumnsFormView.urlname),
    url(r'^session/(?P<session_id>[\w\-]+)/clear/$', clear_session_caches,
        name="data_cleaning_clear_session_caches"),
    url(r'^cases/save/(?P<session_id>[\w\-]+)/$', save_case_session, name='save_case_session'),
    url(r'^form_ids/(?P<session_id>[\w\-]+)/$', download_form_ids, name='download_form_ids'),
]
