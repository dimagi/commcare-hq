from collections import namedtuple
from dimagi.utils.decorators.memoized import memoized

from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation

from .const import STOCK_SECTION_TYPE


_Row = namedtuple('Row', "location stock")


class LedgersByLocationDataSource(object):
    """
    Data source for a report showing ledger values at each location.

                   | Product 1 | Product 2 |
        Location 1 |        76 |        11 |
        Location 2 |       132 |        49 |
    """

    def __init__(self, domain, params=None):
        self.domain = domain
        self.params = params

    @property
    def section_id(self):
        return self.params.get('section_id', STOCK_SECTION_TYPE)

    def _get_rows(self):
        for location in SQLLocation.objects.filter(domain=self.domain):
            # TODO pull out of loop
            stock = (StockState.objects
                     .filter(section_id=self.section_id,
                             sql_location=location)
                     .values_list('sql_product__product_id', 'stock_on_hand'))
            yield _Row(
                location,
                {product_id: soh for product_id, soh in stock}
            )

    @property
    @memoized
    def rows(self):
        return list(self._get_rows())
