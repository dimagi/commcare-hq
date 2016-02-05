from collections import namedtuple
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_lazy
from no_exceptions.exceptions import Http400

from corehq.toggles import SUPPLY_REPORTS
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct

from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport

from .const import STOCK_SECTION_TYPE
from .standard import CommtrackReportMixin

LocationLedger = namedtuple('Row', "location stock")


class LedgersByLocationDataSource(object):
    """
    Data source for a report showing ledger values at each location.

                   | Product 1 | Product 2 |
        Location 1 |        76 |        11 |
        Location 2 |       132 |        49 |
    """

    def __init__(self, domain, section_id, page_start, page_size):
        self.domain = domain
        self.section_id = section_id
        self.page_start = page_start
        self.page_size = page_size

    @property
    @memoized
    def products(self):
        if SQLProduct.objects.filter(domain=self.domain).count() > 20:
            raise Http400("This domain has too many products.")
        return list(SQLProduct.objects.filter(domain=self.domain).order_by('name'))

    def get_locations_queryset(self):
        return (SQLLocation.active_objects
                .filter(domain=self.domain)
                .order_by('name'))

    @property
    @memoized
    def location_rows(self):
        def get_location_ledger(location):
            stock = (StockState.objects
                     .filter(section_id=self.section_id,
                             sql_location=location)
                     .values_list('sql_product__product_id', 'stock_on_hand'))
            return LocationLedger(
                location,
                {product_id: soh for product_id, soh in stock}
            )

        start, stop = self.page_start, self.page_start + self.page_size
        locations = self.get_locations_queryset()[start:stop]
        return map(get_location_ledger, locations)

    @property
    def rows(self):
        for ledger in self.location_rows:
            yield [ledger.location.name] + [
                ledger.stock.get(p.product_id, 0) for p in self.products
            ]

    @property
    def headers(self):
        return [_("Location")] + [p.name for p in self.products]

    @property
    @memoized
    def total_locations(self):
        return self.get_locations_queryset().count()


class LedgersByLocationReport(GenericTabularReport, CommtrackReportMixin):
    name = ugettext_lazy('Ledgers By Location')
    slug = 'ledgers_by_location'
    ajax_pagination = True
    toggles = (SUPPLY_REPORTS,)
    # TODO actually filter by these
    fields = [
        'corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
        'corehq.apps.reports.filters.commtrack.ProgramFilter',
    ]

    @property
    @memoized
    def data(self):
        return LedgersByLocationDataSource(
            domain=self.domain,
            section_id=STOCK_SECTION_TYPE,
            page_start=self.pagination.start,
            page_size=self.pagination.count,
        )

    @property
    def headers(self):
        return DataTablesHeader(
            *[DataTablesColumn(header, sortable=False) for header in self.data.headers]
        )

    @property
    def rows(self):
        return self.data.rows

    @property
    def total_records(self):
        return self.data.total_locations
