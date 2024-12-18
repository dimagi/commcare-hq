from django.core.paginator import Paginator
from django.views.generic.list import ListView

from django_tables2 import SingleTableMixin


class SelectablePaginator(Paginator):
    paging_options = [10, 25, 50, 100]
    default_option = 25


class SelectablePaginatedTableMixin(SingleTableMixin):
    """
    Use this mixin with django-tables2's SingleTableView

    Specify a `urlname` attribute to assist with naming the pagination cookie,
    otherwise the cookie slug will default to using the class name.
    """
    # `paginator_class` should always be a subclass of `SelectablePaginator`
    paginator_class = SelectablePaginator

    @property
    def paginate_by_cookie_slug(self):
        slug = getattr(self, "urlname", self.__class__.__name__)
        return f'{slug}-paginate_by'

    @property
    def default_paginate_by(self):
        return self.request.COOKIES.get(
            self.paginate_by_cookie_slug,
            self.paginator_class.default_option
        )

    @property
    def current_paginate_by(self):
        return self.request.GET.get('per_page', self.default_paginate_by)

    def get_paginate_by(self, table_data):
        return self.current_paginate_by


class SelectablePaginatedTableView(SelectablePaginatedTableMixin, ListView):
    """
    Based on SingleTableView, which inherits from `SingleTableMixin`, `ListView`
    we instead extend the `SingleTableMixin` with `SavedPaginatedTableMixin`.
    """
    template_name = "hqwebapp/tables/single_table.html"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.set_cookie(self.paginate_by_cookie_slug, self.current_paginate_by)
        return response
