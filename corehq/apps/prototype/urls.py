from django.urls import re_path as url
from corehq.apps.prototype.views import example
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
]
