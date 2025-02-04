from django.urls import re_path as url

from corehq.apps.data_cleaning.views import (
    CleanCasesMainView,
    CleanCasesTableView,
)

urlpatterns = [
    url(r'^cases/$', CleanCasesMainView.as_view(), name=CleanCasesMainView.urlname),
    url(r'^cases/table/$', CleanCasesTableView.as_view(), name=CleanCasesTableView.urlname),
]
