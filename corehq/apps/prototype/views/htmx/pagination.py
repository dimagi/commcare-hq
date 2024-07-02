from django.core.paginator import Paginator
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.utils.translation import gettext_lazy
from django_tables2 import columns, tables, SingleTableView

from corehq import toggles
from corehq.apps.hqwebapp.decorators import use_bootstrap5, use_htmx
from corehq.apps.hqwebapp.views import BasePageView
from corehq.apps.prototype.utils import fake_data
from corehq.util.quickcache import quickcache


@method_decorator(use_htmx, name='dispatch')
@method_decorator(use_bootstrap5, name='dispatch')
@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class HtmxPaginationView(BasePageView):
    urlname = "prototype_htmx_pagination_example"
    template_name = 'prototype/htmx/pagination.html'

    @property
    def page_url(self):
        return reverse(self.urlname)


class FakeDataTable(tables.Table):
    css_id = "fake-data-test"
    name = columns.Column(
        verbose_name=gettext_lazy("Name"),
    )
    color = columns.Column(
        verbose_name=gettext_lazy("Color"),
    )
    big_cat = columns.Column(
        verbose_name=gettext_lazy("Big Cats"),
    )
    planet = columns.Column(
        verbose_name=gettext_lazy("Planet"),
    )
    app = columns.Column(
        verbose_name=gettext_lazy("Application"),
    )
    date_opened = columns.Column(
        verbose_name=gettext_lazy("Opened On"),
    )

    class Meta:
        attrs = {
            'class': 'table table-striped',
        }


class SelectablePaginator(Paginator):
    paging_options = [10, 25, 50, 100]


class SavedPaginationOptionMixin(SingleTableView):
    urlname = None
    paginate_by = 25
    paginator_class = SelectablePaginator

    @property
    def paginate_by_cookie_slug(self):
        return f'{self.urlname}-paginate_by'

    @property
    def default_paginate_by(self):
        return self.request.COOKIES.get(self.paginate_by_cookie_slug, self.paginate_by)

    @property
    def current_paginate_by(self):
        return self.request.GET.get('per_page', self.default_paginate_by)

    def get_paginate_by(self, table_data):
        return self.current_paginate_by


class SavedPaginatedTableView(SavedPaginationOptionMixin, SingleTableView):

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response.set_cookie(self.paginate_by_cookie_slug, self.current_paginate_by)
        return response


@method_decorator(toggles.SAAS_PROTOTYPE.required_decorator(), name='dispatch')
class PaginationDataView(SavedPaginatedTableView):
    urlname = "prototype_htmx_table_view"
    table_class = FakeDataTable
    template_name = 'prototype/htmx/single_table.html'

    def get_queryset(self):
        return _generate_example_data(100)

    def get_table_kwargs(self):
        return {
            'template_name': "hqwebapp/tables/bootstrap5_htmx.html",
        }


@quickcache(['num_entries'])
def _generate_example_data(num_entries):
    rows = []
    for row in range(0, num_entries):
        rows.append({
            "name": f"{fake_data.get_first_name()} {fake_data.get_last_name()}",
            "color": fake_data.get_color(),
            "big_cat": fake_data.get_big_cat(),
            "planet": fake_data.get_planet(),
            "app": fake_data.get_fake_app(),
            "date_opened": fake_data.get_past_date(),
        })
    return rows
