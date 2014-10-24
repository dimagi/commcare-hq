from corehq.apps.commtrack.models import SQLProduct
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from django.utils import html
from custom.ilsgateway.models import GroupSummary, SupplyPointStatusTypes
from custom.ilsgateway.reports import ProductAvailabilitySummary, ILSData
from custom.ilsgateway.reports.base_report import MultiReport
from custom.ilsgateway.reports.dashboard_report import SohSubmissionData
from django.utils.translation import ugettext as _


class DetailsReport(MultiReport):
    with_tabs = True

    flush_layout = True

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return True

    @property
    def report_stockonhand_url(self):
        try:
            return html.escape(StockOnHandReport.get_url(
                domain=self.domain) +
                '?location_id=%s&month=%s&year=%s' %
                (self.request_params['location_id'], self.request_params['month'], self.request_params['year']))
        except KeyError:
            return None

    @property
    def report_rand_url(self):
        return 'test2'

    @property
    def report_supervision_url(self):
        return 'test3'

    @property
    def report_delivery_url(self):
        return 'test4'

    @property
    def report_unrecognizedmessages_url(self):
        return 'test5'


class PercentageTableData(ILSData):
    title = 'Percentage'
    slug = 'percentage_table'
    show_chart = False
    show_table = True

    @property
    def headers(self):
        if self.config['products']:
            products = SQLProduct.objects.filter(product_id__in=self.config['products'],
                                                 domain=self.config['domain']).order_by('code')
        else:
            products = SQLProduct.objects.filter(domain=self.config['domain']).order_by('code')
        headers = DataTablesHeader(*[
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('% Facilities Submitting Soh On Time')),
            DataTablesColumn(_('% Facilities Submitting Soh Late')),
            DataTablesColumn(_('% Facilities Not Responding To Soh')),
            DataTablesColumn(_('% Facilities With 1 Or More Stockouts This Month')),
        ])

        for p in products:
            headers.add_column(DataTablesColumn(_('%s stock outs this month') % p.code))

        return headers

    @property
    def rows(self):
        soh_data = []
        if self.config['org_summary']:
            soh_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.SOH_FACILITY,
                                                org_summary=self.config['org_summary'])
        return []


class StockOnHandReport(DetailsReport):
    slug = "stock_on_hand"
    name = 'Stock On Hand'
    title = 'Stock On Hand'
    use_datatables = True

    fields = [AsyncLocationFilter, MonthFilter, YearFilter]

    @property
    def report_config(self):
        config = super(StockOnHandReport, self).report_config
        config.update(dict(products=[]))
        return config

    @property
    def data_providers(self):
        config = self.report_config
        return [
            SohSubmissionData(config=config, css_class='row_chart_all'),
            ProductAvailabilitySummary(config=config, css_class='row_chart_all', chart_stacked=False),
            PercentageTableData(config=config, css_class='row_chart_all')
        ]

    @property
    def report_context(self):
        ret = super(StockOnHandReport, self).report_context
        ret['view_mode'] = 'stockonhand'
        return ret