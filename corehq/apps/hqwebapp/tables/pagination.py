from django.core.paginator import Paginator, InvalidPage
from django.http import Http404, QueryDict
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


class HtmxInvalidPageRedirectMixin:
    """
    This mixin is used to handle the case when the page number served by
    the view is out of range (perhaps when the queryset's filter changes).

    The default behavior of `paginate_queryset` on a `ListView` raises
    an `Http404` exception. This mixin will catch that exception and
    redirect to the first page of the TableView instead.

    IMPORTANT: THIS MIXIN MUST BE THE FIRST IN THE CLASS HIERARCHY.
    Specifically, before `SelectablePaginatedTableView`, which it is often
    used with.

    e.g.:
        class MyTableView(HtmxInvalidPageRedirectMixin, SelectablePaginatedTableView):
            ...
    """

    def paginate_queryset(self, queryset, page_size):
        try:
            return super().paginate_queryset(queryset, page_size)
        except Http404:
            # This is a workaround for the case when the queryset is empty.
            # The default behavior of `paginate_queryset` raises an Http404
            # exception when the page number is out of range.
            raise InvalidPage

    def get_host_url(self):
        """
        This is used to set the `HX-Push-Url` header in the `get_first_page` response.

        :return: str
            The url of the view that is hosting the table view.
        """
        raise NotImplementedError(
            "please return a URL of the view hosting the table view in the "
            "get_host_url() method"
        )

    def get_first_page(self, request, *args, **kwargs):
        """
        We re-render the response instead of a redirect (HttpResponseRedirect)
        because the HX-Push-Url header is ignored by the browser when a redirect
        occurs.
        """
        # sort is the only GET parameter we want to keep
        # when redirecting to the first page
        sort = request.GET.get('sort')
        params = f"sort={sort}" if sort else ""

        # reset the GET parameters to only include sort, no `page` information
        request.GET = QueryDict(params)

        # re-fetch the get response with the modified request
        response = super().get(request, *args, **kwargs)
        params = f"?{params}" if params else ""

        # get the host page url
        host_url = self.get_host_url() + params
        response['HX-Push-Url'] = request.build_absolute_uri(host_url)

        return response

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except InvalidPage:
            return self.get_first_page(request, *args, **kwargs)


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
