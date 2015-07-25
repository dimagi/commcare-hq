from collections import OrderedDict
from datetime import timedelta
from itertools import chain
import datetime
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils.timesince import timesince
from math import ceil
from casexml.apps.stock.models import StockTransaction
from corehq.apps.es import UserES
from corehq import Domain
from corehq.apps.commtrack.models import StockState
from corehq.apps.reports.commtrack.const import STOCK_SECTION_TYPE
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.graph_models import Axis
from custom.common import ALL_OPTION
from custom.ewsghana.filters import ProductByProgramFilter, EWSDateFilter, EWSRestrictionLocationFilter
from custom.ewsghana.models import FacilityInCharge
from custom.ewsghana.reports import EWSData, MultiReport, EWSLineChart, ProductSelectionPane
from custom.ewsghana.utils import has_input_stock_permissions, ews_date_format
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.locations.models import Location, SQLLocation


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
            sql_product__in=self.unique_products(SQLLocation.objects.filter(pk=loc.pk))
        ).order_by('-last_modified_date')

        for state in stock_states:
            if state.daily_consumption:
                monthly_consumption = round(state.get_monthly_consumption())
                max_level = round(monthly_consumption * float(loc.location_type.overstock_threshold))
            else:
                monthly_consumption = None
                max_level = 0

            state_grouping[state.product_id] = {
                'commodity': state.sql_product.name,
                'months_until_stockout': "%.1f" % (float(state.stock_on_hand) / monthly_consumption)
                if state.stock_on_hand and monthly_consumption else 0,
                'stockout_duration': '',
                'stockout_duration_helper': True,
                'current_stock': state.stock_on_hand,
                'monthly_consumption': monthly_consumption,
                'reorder_level': round(max_level / 2.0),
                'maximum_level': max_level,
                'last_report': ews_date_format(state.last_modified_date)
            }

            if state.stock_on_hand == 0:
                try:
                    st = StockTransaction.objects.filter(
                        case_id=loc.supply_point_id,
                        product_id=state.product_id,
                        stock_on_hand__gt=0
                    ).latest('report__date')
                    state_grouping[state.product_id]['stockout_duration'] = timesince(
                        st.report.date, now=datetime.datetime.now()
                    )
                except StockTransaction.DoesNotExist:
                    state_grouping[state.product_id]['stockout_duration'] = 'Always'

            else:
                state_grouping[state.product_id]['stockout_duration_helper'] = False

        for values in state_grouping.values():
            if values['monthly_consumption'] is not None or values['current_stock'] == 0:
                months_until_stockout = get_months_until_stockout_icon(
                    values['months_until_stockout'] if values['months_until_stockout'] else 0.0, loc
                )
            else:
                months_until_stockout = '-'

            if values['monthly_consumption'] and values['monthly_consumption'] != 0.00:
                monthly_consumption = int(values['monthly_consumption'])
            else:
                monthly_consumption = 'not enough data'

            if values['reorder_level'] and values['reorder_level'] != 0.00:
                maximum_level = int(values['reorder_level'])
            else:
                maximum_level = 'unknown'

            if values['maximum_level'] and values['maximum_level'] != 0.00:
                reorder_level = int(values['maximum_level'])
            else:
                reorder_level = 'unknown'

            yield {
                'commodity': values['commodity'],
                'current_stock': int(values['current_stock']) if values['current_stock'] is not None else '--',
                'monthly_consumption': monthly_consumption,
                'months_until_stockout': months_until_stockout,
                'stockout_duration': values['stockout_duration'],
                'last_report': values['last_report'],
                'reorder_level': reorder_level,
                'maximum_level': maximum_level}

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
            sql_product__in=loc.products,
        )

        consumptions = {ss.product_id: ss.daily_consumption for ss in stoke_states}
        st = StockTransaction.objects.filter(
            case_id=loc.supply_point_id,
            sql_product__in=loc.products,
            type='stockonhand',
            report__date__lte=enddate
        ).select_related('report', 'sql_product').order_by('report__date')

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
                chart.add_dataset(product, value,
                                  color='black' if product in ['Understock', 'Overstock'] else None)
            chart.forceY = [0, loc.location_type.understock_threshold + loc.location_type.overstock_threshold]
            chart.is_rendered_as_email = self.config.get('is_rendered_as_email', False)
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


class UsersData(EWSData):
    custom_table = True

    @property
    def rendered_content(self):
        from corehq.apps.users.views.mobile.users import EditCommCareUserView
        users = get_users_by_location_id(self.config['location_id'])
        in_charges = FacilityInCharge.objects.filter(
            location=self.location
        ).values_list('user_id', flat=True)
        district_in_charges = []
        if self.location.parent.location_type.name == 'district':
            children = self.location.parent.get_descendants()
            district_in_charges = list(chain.from_iterable([
                filter(
                    lambda u: 'In Charge' in u.user_data.get('role', []),
                    get_users_by_location_id(child.location_id)
                )
                for child in children
            ]))
        user_to_dict = lambda sms_user: {
            'id': sms_user.get_id,
            'full_name': sms_user.full_name,
            'phone_numbers': sms_user.phone_numbers,
            'in_charge': sms_user.get_id in in_charges,
            'location_name': sms_user.location.sql_location.name,
            'url': reverse(EditCommCareUserView.urlname, args=[self.config['domain'], sms_user.get_id])
        }

        web_users = [
            {
                'id': web_user['_id'],
                'first_name': web_user['first_name'],
                'last_name': web_user['last_name'],
                'email': web_user['email']
            }
            for web_user in UserES().web_users().domain(self.config['domain']).term(
                "domain_memberships.location_id", self.config['location_id']
            ).run().hits
        ]
        return render_to_string('ewsghana/partials/users_tables.html', {
            'users': [user_to_dict(user) for user in users],
            'domain': self.domain,
            'location_id': self.location_id,
            'web_users': web_users,
            'district_in_charges': [user_to_dict(user) for user in district_in_charges]
        })


class StockLevelsReport(MultiReport):
    title = "Aggregate Stock Report"
    fields = [EWSRestrictionLocationFilter, ProductByProgramFilter, EWSDateFilter]
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
                        UsersData(config),
                        InventoryManagementData(config),
                        ProductSelectionPane(config, hide_columns=False)]

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return False
