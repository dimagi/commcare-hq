from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.dbaccessors import get_user_docs_by_location
from corehq.apps.locations.models import SQLLocation
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.sms.models import SMS
from corehq.util.timezones.conversions import ServerTime
from corehq.const import SERVER_DATETIME_FORMAT_NO_SEC
from custom.ilsgateway.models import SupplyPointStatusTypes, ILSNotes
from custom.ilsgateway.tanzania import ILSData, MultiReport
from custom.ilsgateway.tanzania.reports.utils import decimal_format, float_format, latest_status
from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _


class InventoryHistoryData(ILSData):

    title = 'Inventory History'
    slug = 'inventory_history'
    show_chart = False
    show_table = True
    default_rows = 100

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_('Product')),
            DataTablesColumn(_('Stock on Hand')),
            DataTablesColumn(_('Months of stock'))
        )
        return headers

    @property
    def rows(self):
        rows = []
        if self.config['location_id']:
            sp = SQLLocation.objects.get(location_id=self.config['location_id']).supply_point_id
            ss = StockState.objects.filter(
                sql_product__is_archived=False,
                case_id=sp,
                product_id__in=self.config['products']
            )
            for stock in ss:
                def calculate_months_remaining(stock_state, quantity):
                    consumption = stock_state.get_monthly_consumption()
                    if consumption is not None and consumption > 0 and quantity is not None:
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
    searchable = True

    @property
    def title(self):
        return '%s Contacts' % self.config['loc_type']

    @property
    def slug(self):
        return '%s_registration' % self.config['loc_type'].lower()

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('Role')),
            DataTablesColumn(_('Phone')),
            DataTablesColumn(_('Email')),
        )

    @property
    def rows(self):
        location = SQLLocation.objects.get(location_id=self.config['location_id'])
        if self.config['loc_type'] == 'DISTRICT':
            location = location.parent
        elif self.config['loc_type'] == 'REGION':
            location = location.parent.parent

        users = get_user_docs_by_location(self.config['domain'], location.location_id)
        if users:
            for user in users:
                u = user['doc']
                yield [
                    '{0} {1}'.format(u['first_name'], u['last_name']),
                    u['user_data']['role'] if 'role' in u['user_data'] else 'No Role',
                    u['phone_numbers'][0] if u['phone_numbers'] else '',
                    u['email']
                ]


class RandRHistory(ILSData):
    slug = 'randr_history'
    title = 'R & R History'
    show_chart = False
    show_table = True

    @property
    def rows(self):
        return latest_status(self.config['location_id'], SupplyPointStatusTypes.R_AND_R_FACILITY)


class Notes(ILSData):
    slug = 'ils_notes'
    title = 'Notes'
    show_chart = False
    show_table = True
    use_datatables = True

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_('Name')),
            DataTablesColumn(_('Role')),
            DataTablesColumn(_('Date')),
            DataTablesColumn(_('Phone')),
            DataTablesColumn(_('Text'))
        )

    @property
    def rows(self):
        location = SQLLocation.objects.get(location_id=self.config['location_id'])
        rows = ILSNotes.objects.filter(domain=self.config['domain'], location=location).order_by('date')
        for row in rows:
            yield [
                row.user_name,
                row.user_role,
                row.date.strftime(SERVER_DATETIME_FORMAT_NO_SEC),
                row.user_phone,
                row.text
            ]


def _fmt_timestamp(timestamp):
    return dict(
        sort_key=timestamp,
        html=timestamp.strftime("%Y-%m-%d %H:%M:%S"),
    )


def _fmt(val):
    if val is None:
        val = '-'
    return dict(sort_key=val, html=val)


class RecentMessages(ILSData):
    slug = 'recent_messages'
    title = 'Recent messages'
    show_chart = False
    show_table = True
    default_rows = 5
    use_datatables = True

    def __init__(self, config=None):
        super(RecentMessages, self).__init__(config, 'row_chart_all')

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn('Date'),
            DataTablesColumn('User'),
            DataTablesColumn('Phone number'),
            DataTablesColumn('Direction'),
            DataTablesColumn('Text')
        )

    @property
    def rows(self):
        data = (SMS.by_domain(self.config['domain'])
                .filter(location_id=self.config['location_id'])
                .order_by('date'))
        messages = []
        for message in data:
            recipient = message.recipient
            timestamp = ServerTime(message.date).user_time(self.config['timezone']).done()
            messages.append([
                _fmt_timestamp(timestamp),
                recipient.full_name,
                message.phone_number,
                _fmt(message.direction),
                _fmt(message.text),
            ])
        return messages


class FacilityDetailsReport(MultiReport):

    fields = []
    hide_filters = True
    name = "Facility Details"
    slug = 'facility_details'
    use_datatables = True

    @property
    def title(self):
        if self.location and self.location.location_type.name.upper() == 'FACILITY':
            return "{0} ({1}) Group {2}".format(self.location.name,
                                                self.location.site_code,
                                                self.location.metadata.get('group', '---'))
        return 'Facility Details Report'

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return False

    @property
    @memoized
    def data_providers(self):
        config = self.report_config

        return [
            InventoryHistoryData(config=config),
            RandRHistory(config=config),
            Notes(config=config),
            RecentMessages(config=config),
            RegistrationData(config=dict(loc_type='FACILITY', **config), css_class='row_chart_all'),
            RegistrationData(config=dict(loc_type='DISTRICT', **config), css_class='row_chart_all'),
            RegistrationData(config=dict(loc_type='REGION', **config), css_class='row_chart_all')
        ]
