from datetime import datetime, timedelta
from django.utils.timesince import timesince
from math import ceil
from corehq import Domain
from corehq.apps.commtrack.models import StockState
from corehq.apps.products.models import Product
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.commtrack.util import get_relevant_supply_point_ids
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import LineChart, Axis
from corehq.apps.users.models import CommCareUser, CouchUser
from custom.ewsghana.filters import ProductByProgramFilter
from custom.ewsghana.reports import EWSData, REORDER_LEVEL, MAXIMUM_LEVEL, MultiReport
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _
from corehq.apps.locations.models import Location


class StockLevelsSubmissionData(EWSData):
    title = 'Aggregate Stock Report'
    slug = 'stock_levels_submission'
    show_table = True

    @property
    def headers(self):
        headers = DataTablesHeader(*[
            DataTablesColumn(_('Location')),
            DataTablesColumn(_('Stockout')),
            DataTablesColumn(_('Low Stock')),
            DataTablesColumn(_('Adequate Stock')),
            DataTablesColumn(_('Overstock')),
            DataTablesColumn(_('Total'))])

        if self.config['product'] != '':
            headers.add_column(DataTablesColumn(_('AMC')))
        return headers

    def get_prod_data(self):

        for sublocation in self.sublocations:
            sp_ids = get_relevant_supply_point_ids(self.config['domain'], sublocation)
            stock_states = StockState.include_archived.filter(
                case_id__in=sp_ids,
                last_modified_date__lte=self.config['enddate'],
                last_modified_date__gte=self.config['startdate'],
                section_id=STOCK_SECTION_TYPE
            )

            stock_states = stock_states.order_by('product_id')
            state_grouping = {}
            for state in stock_states:
                status = state.stock_category
                if state.product_id in state_grouping:
                    state_grouping[state.product_id][status] += 1
                else:
                    state_grouping[state.product_id] = {
                        'id': state.product_id,
                        'stockout': 0,
                        'understock': 0,
                        'overstock': 0,
                        'adequate': 0,
                        'nodata': 0,
                        'facility_count': 1,
                        'amc': int(state.get_monthly_consumption() or 0)
                    }
                    state_grouping[state.product_id][status] = 1

            location_grouping = {
                'location': sublocation.name,
                'stockout': 0,
                'understock': 0,
                'adequate': 0,
                'overstock': 0,
                'total': 0,
                'amc': 0
            }
            product_ids = []
            if self.config['program'] != '' and self.config['product'] == '':
                product_ids = [product.get_id for product in Product.by_program_id(self.config['domain'],
                                                                                   self.config['program'])]
            elif self.config['program'] != '' and self.config['product'] != '':
                product_ids = [self.config['product']]
            else:
                product_ids = Product.ids_by_domain(self.config['domain'])

            for product in state_grouping.values():
                if product['id'] in product_ids:
                    location_grouping['stockout'] += product['stockout']
                    location_grouping['understock'] += product['understock']
                    location_grouping['adequate'] += product['adequate']
                    location_grouping['overstock'] += product['overstock']
                    location_grouping['total'] += sum([product['stockout'], product['understock'],
                                                       product['adequate'], product['overstock']])
                    location_grouping['amc'] += product['amc']

            location_grouping['stockout'] = self.percent_fn(location_grouping['total'],
                                                            location_grouping['stockout'])
            location_grouping['understock'] = self.percent_fn(location_grouping['total'],
                                                              location_grouping['understock'])
            location_grouping['adequate'] = self.percent_fn(location_grouping['total'],
                                                            location_grouping['adequate'])
            location_grouping['overstock'] = self.percent_fn(location_grouping['total'],
                                                             location_grouping['overstock'])

            yield location_grouping

    @property
    def rows(self):
        for location_grouping in self.get_prod_data():
            row = [location_grouping['location'],
                   location_grouping['stockout'],
                   location_grouping['understock'],
                   location_grouping['adequate'],
                   location_grouping['overstock'],
                   location_grouping['total']]
            if self.config['product'] != '':
                row.append(location_grouping['amc'])

            yield row


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
    title = 'Facility Report'
    slug = 'facility_report'
    show_table = True
    datatables = True

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('Commodity')),
            DataTablesColumn(_('Months Until Stockout')),
            DataTablesColumn(_('Stockout Duration')),
            DataTablesColumn(_('Current Stock')),
            DataTablesColumn(_('Monthly Consumption')),
            DataTablesColumn(_('Reorder Level')),
            DataTablesColumn(_('Maximum Level')),
            DataTablesColumn(_('Date of Last Report'))
        ])

    def get_prod_data(self):
        def get_months_until_stockout_icon(value):
            STOCKOUT = 0.0
            LOW = 1
            ADEQUATE = 3
            if float(value) == STOCKOUT:
                return '%s <span class="icon-remove" style="color:red"/>' % value
            elif float(value) < LOW:
                return '%s <span class="icon-warning-sign" style="color:orange"/>' % value
            elif float(value) <= ADEQUATE:
                return '%s <span class="icon-ok" style="color:green"/>' % value
            elif float(value) > ADEQUATE:
                return '%s <span class="icon-arrow-up" style="color:purple"/>' % value

        state_grouping = {}
        if self.config['program'] and not self.config['product']:
            product_ids = [product.get_id for product in Product.by_program_id(self.config['domain'],
                                                                               self.config['program'])]
        elif self.config['program'] and self.config['product']:
            product_ids = [self.config['product']]
        else:
            product_ids = Product.ids_by_domain(self.config['domain'])

        stock_states = StockState.objects.filter(
            case_id__in=get_relevant_supply_point_ids(self.config['domain'], self.sublocations[0]),
            section_id=STOCK_SECTION_TYPE,
            product_id__in=product_ids
        ).order_by('-last_modified_date')

        for state in stock_states:
            days = (datetime.now() - state.last_modified_date).days
            monthly_consumption = int(state.get_monthly_consumption()) if state.get_monthly_consumption() else 0
            if state.product_id not in state_grouping:
                state_grouping[state.product_id] = {
                    'commodity': Product.get(state.product_id).name,
                    'months_until_stockout': "%.2f" % (days / 30.0) if state.stock_on_hand else '',
                    'months_until_stockout_helper': state.stock_on_hand != 0,
                    'stockout_duration': timesince(state.last_modified_date) if state.stock_on_hand == 0 else '',
                    'stockout_duration_helper': state.stock_on_hand == 0,
                    'current_stock': state.stock_on_hand,
                    'monthly_consumption': monthly_consumption,
                    'reorder_level': int(monthly_consumption * REORDER_LEVEL),
                    'maximum_level': int(monthly_consumption * MAXIMUM_LEVEL),
                    'date_of_last_report': state.last_modified_date.strftime("%Y-%m-%d")
                }
            else:
                if not state_grouping[state.product_id]['months_until_stockout_helper']:
                    if state.stock_on_hand:
                        state_grouping[state.product_id]['months_until_stockout'] = "%.2f" % (days / 30.0)
                    else:
                        state_grouping[state.product_id]['stockout_duration_helper'] = False
                if state_grouping[state.product_id]['stockout_duration_helper']:
                    if not state.stock_on_hand:
                        state_grouping[state.product_id]['stockout_duration'] = timesince(state.last_modified_date)
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

    def get_products(self):
        if self.config['program'] and not self.config['product']:
            product_ids = [product.get_id for product in Product.by_program_id(self.config['domain'],
                                                                               self.config['program'])]
        elif self.config['program'] and self.config['product']:
            product_ids = [self.config['product']]
        else:
            product_ids = Product.ids_by_domain(self.config['domain'])
        return product_ids

    @property
    def rows(self):
        return []

    @property
    def chart_data(self):
        def calculate_weeks_remaining(stock_state, date):

            if stock_state.last_modified_date < date:
                if not stock_state.daily_consumption:
                    return 0
                consumption = float(stock_state.daily_consumption) * 7.0
                quantity = float(stock_state.stock_on_hand) - int((date - state.last_modified_date).days / 7.0) \
                    * consumption
                if consumption and consumption > 0 and quantity > 0:
                    return quantity / consumption
            return 0

        stock_states = StockState.include_archived.filter(
            case_id__in=get_relevant_supply_point_ids(self.config['domain'], self.sublocations[0]),
            section_id=STOCK_SECTION_TYPE,
            product_id__in=self.get_products(),
            last_modified_date__lte=self.config['enddate'],
        ).order_by('last_modified_date')

        rows = {}
        for state in stock_states:
            product_name = Product.get(state.product_id).name
            rows[product_name] = []
            weeks = ceil((self.config['enddate'] - self.config['startdate']).days / 7.0)
            for i in range(1, int(weeks + 1)):
                rows[product_name].append({'x': i, 'y': calculate_weeks_remaining(state, self.config['startdate'] +
                                                                                  timedelta(weeks=i))})
        return rows

    @property
    def charts(self):
        if self.show_chart:
            chart = LineChart("Inventory Management Trends", x_axis=Axis(self.chart_x_label, 'd'),
                              y_axis=Axis(self.chart_y_label, '.1f'))
            for product, value in self.chart_data.iteritems():
                chart.add_dataset(product, value)
            return [chart]
        return []


class StockLevelsReportMixin(object):
    @memoized
    def get_users_by_location_id(self, domain, location_id):
        rows = []
        for user in CommCareUser.by_domain(domain):
            user_number = user.phone_numbers[0] if user.phone_numbers else None
            if user.get_domain_membership(domain).location_id == location_id and user_number:
                rows.append([user.name, user_number])
        return rows


class FacilitySMSUsers(EWSData, StockLevelsReportMixin):
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
        return self.get_users_by_location_id(self.config['domain'], self.config['location_id'])


class FacilityUsers(EWSData, StockLevelsReportMixin):
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
        rows = []
        sms_users = [u[0] for u in self.get_users_by_location_id(self.config['domain'],
                                                                 self.config['location_id'])]
        for user in CouchUser.by_domain(self.config['domain']):
            if user.name not in sms_users:
                if hasattr(user, 'domain_membership') \
                        and user.domain_membership['location_id'] == self.config['location_id']:
                    rows.append([user.name, user.get_email()])
        return rows


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
        rows = []
        for user in CouchUser.by_domain(self.config['domain']):
            if user.user_data.get('role') == 'In Charge' and hasattr(user, 'domain_membership') \
                    and user.domain_membership['location_id'] == self.config['location_id']:
                    rows.append([user.name])
        return rows if rows else [['No data']]


class StockLevelsReport(MultiReport):
    title = "Aggregate Stock Report"
    fields = [AsyncLocationFilter, ProductByProgramFilter, DatespanFilter]
    name = "Stock Levels Report"
    slug = 'ews_stock_levels_report'
    exportable = True

    @property
    def report_config(self):
        program = self.request.GET.get('filter_by_program')
        products = self.request.GET.getlist('filter_by_product')
        return dict(
            domain=self.domain,
            startdate=self.datespan.startdate_utc,
            enddate=self.datespan.enddate_utc,
            location_id=self.request.GET.get('location_id'),
            program=program if program != '0' else None,
            product=products if products and products[0] != '0' else [],
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
                    FacilitySMSUsers(config),
                    FacilityUsers(config),
                    FacilityInChargeUsers(config),
                    InventoryManagementData(config)]
        return [StockLevelsSubmissionData(config)]

    @property
    def export_table(self):
        r = self.report_context['reports'][0]['report_table']
        return [self._export_table(r['title'], r['headers'], r['rows'])]

    def _export_table(self, export_sheet_name, headers, formatted_rows, total_row=None):
        def _unformat_row(row):
            return [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]

        table = headers.as_export_table
        rows = [_unformat_row(row) for row in formatted_rows]
        replace = ''

        for k, v in enumerate(table[0]):
            if v != ' ':
                replace = v
            else:
                table[0][k] = replace
        table.extend(rows)
        if total_row:
            table.append(_unformat_row(total_row))

        return [export_sheet_name, table]
