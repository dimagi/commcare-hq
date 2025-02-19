from django.urls import re_path as url

from corehq.apps.data_cleaning.views.main import (
    CleanCasesMainView,
    CleanCasesSessionView,
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
]
