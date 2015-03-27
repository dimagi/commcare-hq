from collections import defaultdict
from datetime import timedelta
from django.utils.timesince import timesince
from math import ceil
from casexml.apps.stock.models import StockTransaction
from corehq.apps.es import UserES
from corehq import Domain
from corehq.apps.commtrack.models import StockState, CommtrackConfig
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import Axis
from custom.common import ALL_OPTION
from custom.ewsghana.filters import ProductByProgramFilter
from custom.ewsghana.reports import EWSData, REORDER_LEVEL, MAXIMUM_LEVEL, MultiReport, get_url, EWSLineChart, \
    ProductSelectionPane
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _
from corehq.apps.locations.models import Location, SQLLocation
from corehq.apps.locations.models import Location


class StockLevelsLegend(EWSData):
    title = 'Legend'
    slug = 'legend'
    show_table = True

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('Icon')),
            DataTablesColumn(_('Stock status')),
        ])

    @property
    def rows(self):
        return [['<span class="icon-arrow-up" style="color:purple"/>', 'Overstock'],
                ['<span class="icon-ok" style="color:green"/>', 'Adequate'],
                ['<span class="icon-warning-sign" style="color:orange"/>', 'Low'],
                ['<span class="icon-remove" style="color:red"/>', 'Stockout']]


class FacilityReportData(EWSData):
    slug = 'facility_report'
    show_table = True
    use_datatables = True

    @property
    def title(self):
        return 'Facility Report - %s' % SQLLocation.objects.get(location_id=self.config['location_id']).name

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('Commodity')),
            DataTablesColumn(_('Months of Stock')),
            DataTablesColumn(_('Stockout Duration')),
            DataTablesColumn(_('Current Stock')),
            DataTablesColumn(_('Monthly Consumption')),
            DataTablesColumn(_('Reorder Level')),
            DataTablesColumn(_('Maximum Level')),
            DataTablesColumn(_('Date of Last Report'))
        ])

    def get_prod_data(self):
        def get_months_until_stockout_icon(value):
            stock_levels = CommtrackConfig.for_domain(self.config['domain']).stock_levels_config
            if float(value) == 0.0:
                return '%s <span class="icon-remove" style="color:red"/>' % value
            elif float(value) < stock_levels.understock_threshold:
                return '%s <span class="icon-warning-sign" style="color:orange"/>' % value
            elif stock_levels.understock_threshold < float(value) < stock_levels.overstock_threshold:
                return '%s <span class="icon-ok" style="color:green"/>' % value
            elif float(value) >= stock_levels.overstock_threshold:
                return '%s <span class="icon-arrow-up" style="color:purple"/>' % value

        state_grouping = {}

        loc = SQLLocation.objects.get(location_id=self.config['location_id'])

        stock_states = StockState.objects.filter(
            case_id=loc.supply_point_id,
            section_id=STOCK_SECTION_TYPE,
            sql_product__in=self.unique_products([loc])
        ).order_by('-last_modified_date')

        st = StockTransaction.objects.filter(
            case_id=loc.supply_point_id,
            sql_product__in=self.unique_products([loc]),
            type='stockonhand',
        ).order_by('-report__date')

        for state in stock_states:
            monthly_consumption = int(state.get_monthly_consumption()) if state.get_monthly_consumption() else 0
            if state.product_id not in state_grouping:
                state_grouping[state.product_id] = {
                    'commodity': state.sql_product.name,
                    'months_until_stockout': "%.2f" % (state.stock_on_hand / monthly_consumption)
                    if state.stock_on_hand and monthly_consumption else 0,
                    'stockout_duration': '',
                    'stockout_duration_helper': True,
                    'current_stock': state.stock_on_hand,
                    'monthly_consumption': monthly_consumption,
                    'reorder_level': int(monthly_consumption * REORDER_LEVEL),
                    'maximum_level': int(monthly_consumption * MAXIMUM_LEVEL),
                    'date_of_last_report': state.last_modified_date.strftime("%Y-%m-%d")
                }

        for state in st:
            if state_grouping[state.product_id]['stockout_duration_helper']:
                if not state.stock_on_hand:
                    state_grouping[state.product_id]['stockout_duration'] = timesince(state.report.date)
                else:
                    state_grouping[state.product_id]['stockout_duration_helper'] = False

        for values in state_grouping.values():
            yield {
                'commodity': values['commodity'],
                'current_stock': int(values['current_stock']),
                'monthly_consumption': values['monthly_consumption'] if values['monthly_consumption'] != 0.00
                else 'not enough data',
                'months_until_stockout': get_months_until_stockout_icon(values['months_until_stockout']
                                                                        if values['months_until_stockout']
                                                                        else 0.0),
                'stockout_duration': values['stockout_duration'],
                'date_of_last_report': values['date_of_last_report'],
                'reorder_level': values['reorder_level'] if values['reorder_level'] != 0.00
                else 'unknown',
                'maximum_level': values['maximum_level'] if values['maximum_level'] != 0.00
                else 'unknown'}

    @property
    def rows(self):
        for row in self.get_prod_data():
            yield [row['commodity'],
                   row['months_until_stockout'],
                   row['stockout_duration'],
                   row['current_stock'],
                   row['monthly_consumption'],
                   row['reorder_level'],
                   row['maximum_level'],
                   row['date_of_last_report']]


class InventoryManagementData(EWSData):
    title = ''
    slug = 'inventory_management'
    show_table = False
    show_chart = True
    chart_x_label = 'Weeks'
    chart_y_label = 'MOS'

    @property
    def rows(self):
        return []

    @property
    def chart_data(self):
        def calculate_weeks_remaining(state, daily_consumption, date):
            if not daily_consumption:
                return 0
            consumption = float(daily_consumption) * 30.0
            quantity = float(state.stock_on_hand) - int((date - state.report.date).days / 7.0) * consumption
            if consumption and consumption > 0 and quantity > 0:
                return quantity / consumption
            return 0

        loc = SQLLocation.objects.get(location_id=self.config['location_id'])

        stoke_states = StockState.objects.filter(
            case_id=loc.supply_point_id,
            section_id=STOCK_SECTION_TYPE,
            sql_product__in=self.unique_products([loc], all=True),
        )

        consumptions = {ss.product_id: ss.daily_consumption for ss in stoke_states}
        st = StockTransaction.objects.filter(
            case_id=loc.supply_point_id,
            sql_product__in=self.unique_products([loc], all=True),
            type='stockonhand',
            report__date__lte=self.config['enddate']
        ).order_by('report__date')

        rows = defaultdict(dict)
        weeks = ceil((self.config['enddate'] - self.config['startdate']).days / 7.0)
        stock_levels = CommtrackConfig.for_domain(self.config['domain']).stock_levels_config

        for state in st:
            product_name = '{0} ({1})'.format(state.sql_product.name, state.sql_product.code)
            for i in range(1, int(weeks + 1)):
                date = self.config['startdate'] + timedelta(weeks=i)
                if state.report.date < date:
                    rows[product_name][i] = calculate_weeks_remaining(
                        state, consumptions.get(state.product_id, None), date)

        for k, v in rows.iteritems():
            rows[k] = [{'x': key, 'y': value} for key, value in v.iteritems()]

        rows['Understock'] = []
        rows['Overstock'] = []
        for i in range(1, int(weeks + 1)):
            rows['Understock'].append({'x': i, 'y': float(stock_levels.understock_threshold)})
            rows['Overstock'].append({'x': i, 'y': float(stock_levels.overstock_threshold)})

        return rows

    @property
    def charts(self):
        if self.show_chart:
            chart = EWSLineChart("Inventory Management Trends", x_axis=Axis(self.chart_x_label, 'd'),
                                 y_axis=Axis(self.chart_y_label, '.1f'))
            for product, value in self.chart_data.iteritems():
                chart.add_dataset(product, value)
            return [chart]
        return []


class InputStock(EWSData):
    slug = 'input_stock'
    show_table = True

    @property
    def rows(self):
        # TODO: change text to get_url(form_name, "Input Stock", self.config['domain']) and add params
        return [["Input Stock"]]


class FacilitySMSUsers(EWSData):
    title = 'SMS Users'
    slug = 'facility_sms_users'
    show_table = True

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('User')),
            DataTablesColumn(_('Phone Number'))
        ])

    @property
    def rows(self):
        from corehq.apps.users.views.mobile import CreateCommCareUserView

        query = (UserES().mobile_users().domain(self.config['domain'])
                 .term("domain_membership.location_id", self.config['location_id']))

        for hit in query.run().hits:
            if (hit['first_name'] or hit['last_name']) and hit['phone_numbers']:
                yield [hit['first_name'] + ' ' + hit['last_name'], hit['phone_numbers'][0]]

        yield [get_url(CreateCommCareUserView.urlname, 'Create new Mobile Worker', self.config['domain'])]


class FacilityUsers(EWSData):
    title = 'Web Users'
    slug = 'facility_users'
    show_table = True

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('User')),
            DataTablesColumn(_('Email'))
        ])

    @property
    def rows(self):
        query = (UserES().web_users().domain(self.config['domain'])
                 .term("domain_memberships.location_id", self.config['location_id']))

        for hit in query.run().hits:
            if (hit['first_name'] or hit['last_name']) and hit['email']:
                yield [hit['first_name'] + ' ' + hit['last_name'], hit['email']]


class FacilityInChargeUsers(EWSData):
    title = ''
    slug = 'in_charge'
    show_table = True

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('In charge')),
        ])

    @property
    def rows(self):
        query = (UserES().mobile_users().domain(self.config['domain'])
                 .term("domain_membership.location_id", self.config['location_id']))

        for hit in query.run().hits:
            if hit['user_data'].get('role') == 'In Charge' and (hit['first_name'] or hit['last_name']):
                yield [hit['first_name'] + ' ' + hit['last_name']]


class StockLevelsReport(MultiReport):
    title = "Aggregate Stock Report"
    fields = [AsyncLocationFilter, ProductByProgramFilter, DatespanFilter]
    name = "Stock Levels Report"
    slug = 'ews_stock_levels_report'
    exportable = True
    is_exportable = True

    @property
    def report_config(self):
        program = self.request.GET.get('filter_by_program')
        products = self.request.GET.getlist('filter_by_product')
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=self.request.GET.get('location_id'),
            program=program if program != ALL_OPTION else None,
            products=products if products and products[0] != ALL_OPTION else [],
        )

    @property
    @memoized
    def data_providers(self):
        config = self.report_config
        location_types = [loc_type.name for loc_type in filter(
            lambda loc_type: not loc_type.administrative,
            Domain.get_by_name(self.domain).location_types
        )]
        if not self.needs_filters and Location.get(config['location_id']).location_type in location_types:
            return [FacilityReportData(config),
                    StockLevelsLegend(config),
                    InputStock(config),
                    FacilitySMSUsers(config),
                    FacilityUsers(config),
                    FacilityInChargeUsers(config),
                    InventoryManagementData(config),
                    ProductSelectionPane(config)]

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return False
