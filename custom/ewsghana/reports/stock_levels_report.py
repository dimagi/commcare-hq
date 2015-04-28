from collections import OrderedDict
from datetime import timedelta
from django.core.urlresolvers import reverse
from django.utils.timesince import timesince
from math import ceil
from casexml.apps.stock.models import StockTransaction
from corehq.apps.es import UserES
from corehq import Domain
from corehq.apps.commtrack.models import StockState
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.reports.graph_models import Axis
from corehq.apps.users.models import CommCareUser
from custom.common import ALL_OPTION
from custom.ewsghana.filters import ProductByProgramFilter
from custom.ewsghana.reports import EWSData, MultiReport, get_url_with_location, EWSLineChart, ProductSelectionPane
from custom.ewsghana.utils import has_input_stock_permissions
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _
from corehq.apps.locations.models import Location, SQLLocation
from dimagi.utils.parsing import json_format_date


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
        def get_months_until_stockout_icon(value, loc):
            if float(value) == 0.0:
                return '%s <span class="icon-remove" style="color:red"/>' % value
            elif float(value) < loc.location_type.understock_threshold:
                return '%s <span class="icon-warning-sign" style="color:orange"/>' % value
            elif loc.location_type.understock_threshold < float(value) < loc.location_type.overstock_threshold:
                return '%s <span class="icon-ok" style="color:green"/>' % value
            elif float(value) >= loc.location_type.overstock_threshold:
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
            report__date__lte=self.config['enddate'],
            type='stockonhand',
        ).order_by('-report__date')

        for state in stock_states:
            monthly_consumption = round(state.get_monthly_consumption()) if state.get_monthly_consumption() else 0
            max_level = round(monthly_consumption * float(loc.location_type.overstock_threshold))
            if state.product_id not in state_grouping:
                state_grouping[state.product_id] = {
                    'commodity': state.sql_product.name,
                    'months_until_stockout': "%.2f" % (float(state.stock_on_hand) / monthly_consumption)
                    if state.stock_on_hand and monthly_consumption else 0,
                    'stockout_duration': '',
                    'stockout_duration_helper': True,
                    'current_stock': None,
                    'monthly_consumption': monthly_consumption,
                    'reorder_level': round(max_level / 2.0),
                    'maximum_level': max_level,
                    'last_report': ''
                }

        for state in st:
            if state_grouping[state.product_id]['stockout_duration_helper']:
                if not state.stock_on_hand:
                    state_grouping[state.product_id]['stockout_duration'] = timesince(state.report.date,
                                                                                      now=self.config['enddate'])
                else:
                    state_grouping[state.product_id]['stockout_duration_helper'] = False

                if not state_grouping[state.product_id]['last_report']:
                    state_grouping[state.product_id]['last_report'] = json_format_date(state.report.date)
                if state_grouping[state.product_id]['current_stock'] is None:
                    state_grouping[state.product_id]['current_stock'] = state.stock_on_hand


        for values in state_grouping.values():
            yield {
                'commodity': values['commodity'],
                'current_stock': int(values['current_stock'] or 0),
                'monthly_consumption': values['monthly_consumption'] if values['monthly_consumption'] != 0.00
                else 'not enough data',
                'months_until_stockout': get_months_until_stockout_icon(values['months_until_stockout']
                                                                        if values['months_until_stockout']
                                                                        else 0.0, loc),
                'stockout_duration': values['stockout_duration'],
                'last_report': values['last_report'],
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
                   row['last_report']]


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
            consumption = round(float(daily_consumption) * 30.0)
            quantity = float(state.stock_on_hand) - int((date - state.report.date).days / 7.0) * consumption
            if consumption and consumption > 0 and quantity > 0:
                return quantity / consumption
            return 0

        enddate = self.config['enddate']
        startdate = self.config['startdate'] if 'custom_date' in self.config else enddate - timedelta(days=30)

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
            report__date__lte=enddate
        ).order_by('report__date')

        rows = OrderedDict()
        weeks = ceil((enddate - startdate).days / 7.0)

        for state in st:
            product_name = '{0} ({1})'.format(state.sql_product.name, state.sql_product.code)
            if product_name not in rows:
                rows[product_name] = {}
            for i in range(1, int(weeks + 1)):
                date = startdate + timedelta(weeks=i)
                if state.report.date < date:
                    rows[product_name][i] = calculate_weeks_remaining(
                        state, consumptions.get(state.product_id, None), date)

        for k, v in rows.iteritems():
            rows[k] = [{'x': key, 'y': value} for key, value in v.iteritems()]

        rows['Understock'] = []
        rows['Overstock'] = []
        for i in range(1, int(weeks + 1)):
            rows['Understock'].append({'x': i, 'y': float(loc.location_type.understock_threshold)})
            rows['Overstock'].append({'x': i, 'y': float(loc.location_type.overstock_threshold)})

        return rows

    @property
    def charts(self):
        if self.show_chart:
            loc = SQLLocation.objects.get(location_id=self.config['location_id'])
            chart = EWSLineChart("Inventory Management Trends", x_axis=Axis(self.chart_x_label, 'd'),
                                 y_axis=Axis(self.chart_y_label, '.1f'))
            chart.height = 600
            values = []
            for product, value in self.chart_data.iteritems():
                values.extend([a['y'] for a in value])
                chart.add_dataset(product, value, color='red' if product in ['Understock', 'Overstock'] else None)
            chart.forceY = [0, loc.location_type.understock_threshold + loc.location_type.overstock_threshold]
            return [chart]
        return []


class InputStock(EWSData):
    slug = 'input_stock'
    show_table = True

    @property
    def rows(self):
        link = reverse('input_stock', args=[self.domain, self.location.site_code])
        transactions = StockTransaction.objects.filter(
            case_id=self.location.supply_point_id,
            report__date__lte=self.config['enddate']
        ).order_by('-report__date', 'pk')
        rows = []

        if has_input_stock_permissions(self.config['user'],
                                       SQLLocation.objects.get(location_id=self.config['location_id']),
                                       self.domain):
            rows.append([u"<a href='{}'>INPUT STOCK for {}</a>".format(link, self.location.name)])

        if transactions:
            rows.append(
                [
                    u'The last report received was at <b>{}.</b>'.format(
                        transactions[0].report.date.strftime("%X on %b %d, %Y")
                    )
                ]
            )

        return rows


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

        users = CommCareUser.view(
            'locations/users_by_location_id',
            startkey=[self.config['location_id']],
            endkey=[self.config['location_id'], {}],
            include_docs=True
        ).all()

        for user in users:
            if user.full_name and user.phone_numbers:
                yield ['<div val="%s" sel=%s>%s</div>' % (
                    user._id, 'true' if user.user_data.get('role') == 'In Charge' else 'false',
                    user.full_name), user.phone_numbers[0]]

        yield [get_url_with_location(CreateCommCareUserView.urlname, 'Create new Mobile Worker',
                                     self.config['location_id'], self.config['domain'])]


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
        users = CommCareUser.view(
            'locations/users_by_location_id',
            startkey=[self.config['location_id']],
            endkey=[self.config['location_id'], {}],
            include_docs=True
        ).all()

        for user in users:
            if user.user_data.get('role') == 'In Charge' and user.full_name:
                yield [user.full_name]
        yield ['<button id="in-charge-button" class="btn" data-target="#configureInCharge" data-toggle="modal">'
               'Configure In Charge</button>']


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
            user=self.request.couch_user
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
            if self.is_rendered_as_email:
                return [FacilityReportData(config)]
            else:
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
