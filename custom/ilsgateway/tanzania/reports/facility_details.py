from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.apps.users.models import CommCareUser
from custom.ilsgateway.tanzania.reports import ILSData
from custom.ilsgateway.tanzania.reports.base_report import MultiReport
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _


def decimal_format(value):
    if value == 0:
        return '<span class="icon-remove" style="color:red"/> %.0f' % value
    elif not value:
        return '<span style="color:grey"/> No Data'
    else:
        return '%.0f' % value


def float_format(value):
    if value == 0:
        return '<span class="icon-remove" style="color:red"/> %.2f' % value
    elif not value:
        return '<span style="color:grey">No Data</span>'
    else:
        return '%.2f' % value


class InventoryHistoryData(ILSData):

    title = 'Inventory History'
    slug = 'inventory_history'
    show_chart = False
    show_table = True

    @property
    def headers(self):
        headers = DataTablesHeader(*[
            DataTablesColumn(_('Product')),
            DataTablesColumn(_('Stock on Hand')),
            DataTablesColumn(_('Months of stock'))
        ])
        return headers

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            sp = SQLLocation.objects.get(location_id=self.config['location_id']).supply_point_id
            ss = StockState.objects.filter(sql_product__is_archived=False, case_id=sp)
            for stock in ss:
                def calculate_months_remaining(stock_state, quantity):
                    consumption = stock_state.get_monthly_consumption()
                    if consumption is not None and consumption > 0 \
                      and quantity is not None:
                        return float(quantity) / float(consumption)
                    elif quantity == 0:
                        return 0
                    return None
                rows.append([stock.sql_product.name, decimal_format(stock.stock_on_hand),
                             float_format(calculate_months_remaining(stock, stock.stock_on_hand))])
        return rows


class RegistrationData(ILSData):
    show_chart = False
    show_table = True

    @property
    def title(self):
        return '%s Contacts' % self.config['loc_type']

    @property
    def slug(self):
        return '%s_registration' % self.config['loc_type'].lower()

    @property
    def headers(self):
        return DataTablesHeader(*[
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('Role')),
            DataTablesColumn(_('Phone')),
            DataTablesColumn(_('Email')),
        ])

    @property
    def rows(self):
        users_in_domain = CommCareUser.by_domain(domain=self.config['domain'])
        location = SQLLocation.objects.get(location_id=self.config['location_id'])
        if self.config['loc_type'] == 'DISTRICT':
            location = location.parent
        elif self.config['loc_type'] == 'REGION':
            location = location.parent.parent

        users = [user for user in users_in_domain if user.get_domain_membership(self.config['domain']).location_id
                 == location.location_id]
        if users:
            return [[u.full_name, u.user_data['role'], u.phone_number, u.email] for u in users]
        

class FacilityDetailsReport(MultiReport):

    title = "Facility Details Report"
    fields = [AsyncLocationFilter]
    name = "Facility Details"
    slug = 'facility_details'
    use_datatables = True

    @property
    @memoized
    def data_providers(self):
        config = self.report_config

        return [
            InventoryHistoryData(config=config, css_class='row_chart_all'),
            RegistrationData(config=dict(loc_type='FACILITY', **config), css_class='row_chart_all'),
            RegistrationData(config=dict(loc_type='DISTRICT', **config), css_class='row_chart_all'),
            RegistrationData(config=dict(loc_type='REGION', **config), css_class='row_chart_all')
        ]