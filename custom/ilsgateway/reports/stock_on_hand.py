from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import SQLProduct
from corehq.apps.locations.models import Location
from corehq.apps.reports.commtrack.util import get_relevant_supply_point_ids
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.filters.select import MonthFilter, YearFilter
from django.utils import html
from custom.ilsgateway.models import GroupSummary, SupplyPointStatusTypes, ProductAvailabilityData, \
    OrganizationSummary
from custom.ilsgateway.reports import ProductAvailabilitySummary, ILSData, format_percent, link_format
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


class SohPercentageTableData(ILSData):
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
        rows = []
        if not self.config['products']:
            prd_id = [p.product_id for p in
                      SQLProduct.objects.filter(domain=self.config['domain']).order_by('code')]
        else:
            prd_id = self.config['products']

        if self.config['location_id']:

            location = Location.get(self.config['location_id'])
            for loc in location.children:
                org_summary = OrganizationSummary.objects.filter(date__range=(self.config['startdate'],
                                                              self.config['enddate']),
                                                 supply_point=loc._id)[0]

                soh_data = GroupSummary.objects.get(title=SupplyPointStatusTypes.SOH_FACILITY,
                                                org_summary=org_summary)
                facs = Location.filter_by_type(self.config['domain'], 'FACILITY', loc)
                facs_count = (float(len(list(facs))) or 1)
                soh_on_time = soh_data.on_time * 100 / facs_count
                soh_late = soh_data.late * 100 / facs_count
                soh_not_responding = soh_data.not_responding * 100 / facs_count
                fac_ids = get_relevant_supply_point_ids(self.config['domain'], loc)
                stockouts = (StockTransaction.objects.filter(
                    case_id__in=fac_ids, quantity__lte=0,
                    report__date__month=int(self.config['month']),
                    report__date__year=int(self.config['year'])).count() or 0) / facs_count
                try:
                    url = html.escape(StockOnHandReport.get_url(
                        domain=self.config['domain']) +
                        '?location_id=%s&month=%s&year=%s' %
                        (loc._id, self.config['month'], self.config['year']) +
                        '&products='.join(self.config['products']))
                except KeyError:
                    url = None

                row_data = [
                    link_format(loc.name, url),
                    format_percent(soh_on_time),
                    format_percent(soh_late),
                    format_percent(soh_not_responding),
                    format_percent(stockouts)
                ]

                for product in prd_id:
                    ps = ProductAvailabilityData.objects.filter(
                        supply_point=loc._id,
                        product=product,
                        date=self.config['startdate'])
                    if ps:
                        row_data.append(format_percent(ps[0].without_stock * 100 / float(ps[0].total)))
                    else:
                        row_data.append("<span class='no_data'>None</span>")
                rows.append(row_data)

        return rows


class DistrictSohPercentageTableData(ILSData):
    title = 'Percentage'
    slug = 'district_percentage_table'
    show_chart = False
    show_table = True

    @property
    def headers(self):
        return []

    @property
    def rows(self):
        rows = []
        return rows


class StockOnHandReport(DetailsReport):
    slug = "stock_on_hand"
    name = 'Stock On Hand'
    title = 'Stock On Hand'
    use_datatables = True

    fields = [AsyncLocationFilter, MonthFilter, YearFilter]

    @property
    def report_config(self):
        config = super(StockOnHandReport, self).report_config
        # TODO add support for product filter
        config.update(dict(products=[]))
        return config

    @property
    def data_providers(self):
        config = self.report_config

        location = Location.get(config['org_summary'].supply_point)

        data_providers = [
            SohSubmissionData(config=config, css_class='row_chart_all'),
            ProductAvailabilitySummary(config=config, css_class='row_chart_all', chart_stacked=False),
        ]

        if location.location_type.upper() == 'DISTRICT':
            data_providers.append(DistrictSohPercentageTableData(config=config, css_class='row_chart_all'))
        else:
            data_providers.append(SohPercentageTableData(config=config, css_class='row_chart_all'))
        return data_providers

    @property
    def report_context(self):
        ret = super(StockOnHandReport, self).report_context
        ret['view_mode'] = 'stockonhand'
        return ret