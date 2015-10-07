from collections import namedtuple
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_lazy
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from no_exceptions.exceptions import Http400

from corehq.toggles import SUPPLY_REPORTS
from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.apps.style.decorators import use_bootstrap3

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

    @property
    @memoized
    def products(self):
        if SQLProduct.objects.filter(domain=self.domain).count() > 20:
            raise Http400("This domain has too many products.")
        return list(SQLProduct.objects.filter(domain=self.domain))

    def _get_rows(self):
        for location in SQLLocation.objects.filter(domain=self.domain).order_by('name'):
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


class LedgersByLocationReport(TemplateView):
    name = ugettext_lazy('Ledgers By Location')
    urlname = 'ledgers_by_location'
    template_name = 'style/bootstrap3/base_section.html'
    asynchronous = True
    fields = [
        'corehq.apps.reports.filters.fixtures.AsyncLocationFilter',
        'corehq.apps.reports.dont_use.fields.SelectProgramField',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]
    #  TODO?
    #  exportable = True
    #  emailable = True

    @method_decorator(use_bootstrap3())
    @method_decorator(SUPPLY_REPORTS.required_decorator())
    def dispatch(self, request, domain, **kwargs):
        self.domain = domain
        return super(LedgersByLocationReport, self).dispatch(request, domain, **kwargs)

    def get_context_data(self):
        #  TODO accommodate `format_sidebar` context
        return {
            'domain': self.domain,
            'section': {'url': '/path/to/page/', 'page_name': self.name},
            'current_page': {
                'url': '/path/',
                'parents': [],
                'page_name': self.name,  # the same...
                'title': self.name,
            },
            'couch_user': self.request.couch_user,
            'view': self,
        }

    @staticmethod
    def show_in_navigation(domain, project, user=None):
        return project.commtrack_enabled and SUPPLY_REPORTS.enabled(domain)
