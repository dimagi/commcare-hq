from django.urls import re_path as url
from corehq.apps.prototype.views import example
from corehq.apps.prototype.views import webpack
from corehq.apps.prototype.views.data_cleaning.main import (
    CaseDataCleaningPrototypeView,
    reset_data,
    slow_simulator,
)
from corehq.apps.prototype.views.data_cleaning.forms import (
    ConfigureColumnsFormView,
    FilterColumnsFormView,
    CleanDataFormView,
)
from corehq.apps.prototype.views.data_cleaning.tables import (
    DataCleaningTableView,
)
from corehq.apps.prototype.views.htmx.pagination import (
    HtmxPaginationView,
    PaginationDataView,
)

urlpatterns = [
    url(r'^webpack/b5_amd/$', webpack.bootstrap5_amd_example,
        name='webpack_bootstrap5_amd_example'),
    url(r'^webpack/b3_amd/$', webpack.bootstrap3_amd_example,
        name='webpack_bootstrap3_amd_example'),
    url(r'^webpack/pagination/$', webpack.knockout_pagination,
        name='webpack_knockout_pagination'),
    url(r'^example/$', example.knockout_pagination,
        name='prototype_example_knockout_pagination'),
    url(r'^example/data/$', example.example_paginated_data,
        name='prototype_example_paginated_data'),
    url(r'^htmx/pagination/$', HtmxPaginationView.as_view(),
        name=HtmxPaginationView.urlname),
    url(r'^htmx/pagination/data/$', PaginationDataView.as_view(),
        name=PaginationDataView.urlname),
    url(r'^htmx/cleaning/$', CaseDataCleaningPrototypeView.as_view(),
        name=CaseDataCleaningPrototypeView.urlname),
    url(r'^htmx/cleaning/data/$', DataCleaningTableView.as_view(),
        name=DataCleaningTableView.urlname),
    url(r'^htmx/cleaning/forms/columns/$', ConfigureColumnsFormView.as_view(),
        name=ConfigureColumnsFormView.urlname),
    url(r'^htmx/cleaning/forms/filter/$', FilterColumnsFormView.as_view(),
        name=FilterColumnsFormView.urlname),
    url(r'^htmx/cleaning/forms/clean_data/$', CleanDataFormView.as_view(),
        name=CleanDataFormView.urlname),
    url(r'^htmx/cleaning/reset/$', reset_data,
        name="data_cleaning_reset_data"),
    url(r'^htmx/cleaning/slow/$', slow_simulator,
        name="data_cleaning_slow"),
]
