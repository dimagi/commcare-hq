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
    url(r'^dc/$', CaseDataCleaningPrototypeView.as_view(),
        name=CaseDataCleaningPrototypeView.urlname),
    url(r'^dc/data/$', DataCleaningTableView.as_view(),
        name=DataCleaningTableView.urlname),
    url(r'^dc/forms/columns/$', ConfigureColumnsFormView.as_view(),
        name=ConfigureColumnsFormView.urlname),
    url(r'^dc/forms/filter/$', FilterColumnsFormView.as_view(),
        name=FilterColumnsFormView.urlname),
    url(r'^dc/forms/clean_data/$', CleanDataFormView.as_view(),
        name=CleanDataFormView.urlname),
    url(r'^dc/reset/$', reset_data,
        name="data_cleaning_reset_data"),
    url(r'^dc/slow/$', slow_simulator,
        name="data_cleaning_slow"),
]
