from django.urls import re_path as url
from corehq.apps.prototype.views import example
from corehq.apps.prototype.views.data_cleaning.main import (
    DataCleaningPrototypeView,
)
from corehq.apps.prototype.views.data_cleaning.forms import (
    ConfigureColumnsFormView,
    FilterColumnsFormView,
)
from corehq.apps.prototype.views.data_cleaning.tables import (
    DataCleaningTableView,
)
from corehq.apps.prototype.views.htmx.pagination import (
    HtmxPaginationView,
    PaginationDataView,
)

urlpatterns = [
    url(r'^example/$', example.knockout_pagination,
        name='prototype_example_knockout_pagination'),
    url(r'^example/data/$', example.example_paginated_data,
        name='prototype_example_paginated_data'),
    url(r'^htmx/pagination/$', HtmxPaginationView.as_view(),
        name=HtmxPaginationView.urlname),
    url(r'^htmx/pagination/data/$', PaginationDataView.as_view(),
        name=PaginationDataView.urlname),
    url(r'^htmx/cleaning/$', DataCleaningPrototypeView.as_view(),
        name=DataCleaningPrototypeView.urlname),
    url(r'^htmx/cleaning/data/$', DataCleaningTableView.as_view(),
        name=DataCleaningTableView.urlname),
    url(r'^htmx/cleaning/forms/columns/$', ConfigureColumnsFormView.as_view(),
        name=ConfigureColumnsFormView.urlname),
    url(r'^htmx/cleaning/forms/filter/$', FilterColumnsFormView.as_view(),
        name=FilterColumnsFormView.urlname),
]
