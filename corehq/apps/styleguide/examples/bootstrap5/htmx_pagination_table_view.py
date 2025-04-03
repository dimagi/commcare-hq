from corehq.apps.hqwebapp.tables.pagination import SelectablePaginatedTableView
from corehq.apps.styleguide.examples.bootstrap5.htmx_pagination_data import generate_example_pagination_data
from corehq.apps.styleguide.examples.bootstrap5.htmx_pagination_table import ExampleFakeDataTable


class ExamplePaginatedTableView(SelectablePaginatedTableView):
    """
    This view returns a partial template of a table, along with its
    page controls and page size selection. Its parent classes handle
    pagination of a given queryset based on GET parameters in the request.

    This view will be fetched by the "host" `HtmxPaginationView`
    via an HTMX GET request.
    """
    urlname = "styleguide_b5_paginated_table_view"
    table_class = ExampleFakeDataTable

    def get_queryset(self):
        return generate_example_pagination_data(100)
