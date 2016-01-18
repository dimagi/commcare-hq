from collections import namedtuple
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from django.db.models.query_utils import Q
from corehq.apps.accounting import generator
from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, SoftwarePlanEdition, Subscription
from corehq.apps.commtrack.models import StockState
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.models import SQLLocation, LocationType, Location
from datetime import timedelta, datetime
from dateutil import rrule
from dateutil.rrule import MO
from django.utils import html
from corehq.apps.sms.mixin import VerifiedNumber, BackendMapping
from corehq.form_processor.interfaces.supply import SupplyInterface
from corehq.messaging.smsbackends.test.models import TestSMSBackend
from corehq.util.quickcache import quickcache
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import add_msg_tags, send_sms_to_verified_number, send_sms as core_send_sms
from corehq.apps.sms.models import SMSLog, OUTGOING
from corehq.apps.users.models import CommCareUser, WebUser, UserRole
from custom.ewsghana.models import EWSGhanaConfig, EWSExtension
from custom.ewsghana.reminders.const import DAYS_UNTIL_LATE

TEST_DOMAIN = 'ewsghana-receipts-test'
TEST_BACKEND = 'MOBILE_BACKEND_TEST'
Msg = namedtuple('Msg', ['text'])


def get_descendants(location_id):
    return SQLLocation.objects.get(
        location_id=location_id
    ).get_descendants().exclude(supply_point_id__isnull=True).exclude(is_archived=True)


def get_second_week(start_date, end_date):
    mondays = list(rrule.rrule(rrule.MONTHLY, dtstart=start_date, until=end_date, byweekday=(MO,), bysetpos=2))
    for monday in mondays:
        yield {
            'start_date': monday,
            'end_date': monday + timedelta(days=6)
        }


def make_url(report_class, domain, string_params, args):
    try:
        return html.escape(
            report_class.get_url(
                domain=domain
            ) + string_params % args
        )
    except KeyError:
        return None


# Calculate last full period (Friday - thursday)
def calculate_last_period(enddate=None):
    if not enddate:
        enddate = datetime.utcnow()
    last_friday = enddate - timedelta(days=(enddate.weekday() - 4) % 7)
    last_friday = last_friday.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_next_thursday = (last_friday + timedelta(days=7)) - timedelta(microseconds=1)
    return last_friday, end_of_next_thursday


def send_test_message(verified_number, text, metadata=None):
    msg = SMSLog(
        couch_recipient_doc_type=verified_number.owner_doc_type,
        couch_recipient=verified_number.owner_id,
        phone_number="+" + str(verified_number.phone_number),
        direction=OUTGOING,
        date=datetime.utcnow(),
        domain=verified_number.domain,
        text=text,
        processed=True,
        datetime_to_process=datetime.utcnow(),
        queued_timestamp=datetime.utcnow()
    )
    msg.save()
    add_msg_tags(msg, metadata)
    return True


def get_products_ids_assigned_to_rel_sp(domain, active_location=None):

    def filter_relevant(queryset):
        return queryset.filter(
            supply_point_id__isnull=False
        ).values_list(
            'products__product_id',
            flat=True
        )

    if active_location:
        sql_location = active_location.sql_location
        products = []
        if sql_location.supply_point_id:
            products.append(sql_location.products.values_list('product_id', flat=True))
        products += list(
            filter_relevant(sql_location.get_descendants())
        )

        return products
    else:
        return filter_relevant(SQLLocation.objects.filter(domain=domain, is_archived=False))


def make_loc(code, name, domain, type, parent=None):
    name = name or code
    sql_type, _ = LocationType.objects.get_or_create(domain=domain, name=type)
    loc = Location(site_code=code, name=name, domain=domain, location_type=type, parent=parent)
    loc.save()

    if not sql_type.administrative:
        SupplyInterface.create_from_location(domain, loc)
        loc.save()

    sql_location = loc.sql_location
    sql_location.products = []
    sql_location.save()
    return loc


def assign_products_to_location(location, products):
    sql_location = location.sql_location
    sql_location.products = [SQLProduct.objects.get(product_id=product.get_id) for product in products]
    sql_location.save()


def create_backend():
    backend = TestSMSBackend(
        domain=None,
        name=TEST_BACKEND,
        authorized_domains=[],
        is_global=True,
    )
    backend._id = backend.name
    backend.save()
    sms_backend_mapping = BackendMapping(is_global=True, prefix="*", backend_id=backend.get_id)
    sms_backend_mapping.save()
    return sms_backend_mapping, backend


def prepare_domain(domain_name):
    domain = create_domain(domain_name)
    domain.convert_to_commtrack()

    domain.default_sms_backend_id = TEST_BACKEND
    domain.save()

    def _make_loc_type(name, administrative=False, parent_type=None):
        return LocationType.objects.get_or_create(
            domain=domain_name,
            name=name,
            administrative=administrative,
            parent_type=parent_type,
        )[0]

    country = _make_loc_type(name="country", administrative=True)
    _make_loc_type(name="Central Medical Store", parent_type=country)
    _make_loc_type(name="Teaching Hospital", parent_type=country)

    region = _make_loc_type(name="region", administrative=True, parent_type=country)
    _make_loc_type(name="Regional Medical Store", parent_type=region)
    _make_loc_type(name="Regional Hospital", parent_type=region)

    district = _make_loc_type(name="district", administrative=True, parent_type=region)
    _make_loc_type(name="Clinic", parent_type=district)
    _make_loc_type(name="District Hospital", parent_type=district)
    _make_loc_type(name="Health Centre", parent_type=district)
    _make_loc_type(name="CHPS Facility", parent_type=district)
    _make_loc_type(name="Hospital", parent_type=district)
    _make_loc_type(name="Psychiatric Hospital", parent_type=district)
    _make_loc_type(name="Polyclinic", parent_type=district)
    _make_loc_type(name="facility", parent_type=district)

    generator.instantiate_accounting_for_tests()
    account = BillingAccount.get_or_create_account_by_domain(
        domain.name,
        created_by="automated-test",
    )[0]
    plan = DefaultProductPlan.get_default_plan_by_domain(
        domain, edition=SoftwarePlanEdition.ADVANCED
    )
    subscription = Subscription.new_domain_subscription(
        account,
        domain.name,
        plan
    )
    subscription.is_active = True
    subscription.save()
    ews_config = EWSGhanaConfig(enabled=True, domain=domain.name)
    ews_config.save()
    return domain

TEST_LOCATION_TYPE = 'outlet'
TEST_USER = 'commtrack-user'
TEST_NUMBER = '5551234'
TEST_PASSWORD = 'secret'


def bootstrap_user(username=TEST_USER, domain=TEST_DOMAIN,
                   phone_number=TEST_NUMBER, password=TEST_PASSWORD,
                   backend=TEST_BACKEND, first_name='', last_name='',
                   home_loc=None, user_data=None, program_id=None
                   ):
    user_data = user_data or {}
    user = CommCareUser.create(
        domain,
        username,
        password,
        phone_numbers=[phone_number],
        user_data=user_data,
        first_name=first_name,
        last_name=last_name
    )
    if home_loc:
        user.set_location(home_loc)
    dm = user.get_domain_membership(domain)
    dm.program_id = program_id
    user.save()

    user.save_verified_number(domain, phone_number, verified=True, backend_id=backend)
    return CommCareUser.wrap(user.to_json())


def bootstrap_web_user(domain, username, password, email, location, user_data=None, phone_number="", first_name="",
                       last_name="", program_id=None):
    web_user = WebUser.create(
        domain=domain,
        username=username,
        password=password,
        email=email
    )

    web_user.first_name = first_name
    web_user.last_name = last_name

    web_user.user_data = user_data or {}
    web_user.set_location(domain, location)
    dm = web_user.get_domain_membership(domain)
    dm.program_id = program_id
    if phone_number:
        web_user.phone_numbers = [phone_number]
    web_user.save()
    return web_user

REORDER_LEVEL = Decimal("1.5")


class ProductsReportHelper(object):

    def __init__(self, location, transactions):
        self.location = location
        self.transactions = transactions

    def reported_products_ids(self):
        return {transaction.product_id for transaction in self.transactions}

    def reported_products(self):
        return SQLProduct.objects.filter(product_id__in=self.reported_products_ids())

    def missing_products(self):
        products_ids = SQLProduct.objects.filter(
            domain=self.location.domain,
            is_archived=False
        ).values_list('product_id')
        date = datetime.utcnow() - timedelta(days=7)
        earlier_reported_products = StockState.objects.filter(
            product_id__in=products_ids,
            case_id=self.location.supply_point_id
        ).exclude(last_modified_date__lte=date).values_list('product_id', flat=True).distinct()
        missing_products = self.location.products.distinct().values_list(
            'product_id', flat=True
        ).exclude(product_id__in=earlier_reported_products).exclude(product_id__in=self.reported_products_ids())
        if not missing_products:
            return []
        return SQLProduct.objects.filter(product_id__in=missing_products)

    def stock_states(self):
        product_ids = [product.product_id for product in self.reported_products()]
        return StockState.objects.filter(
            product_id__in=product_ids,
            case_id=self.location.supply_point_id
        )

    def stockouts(self):
        return self.stock_states().filter(
            stock_on_hand=0
        ).distinct('sql_product__code').order_by('sql_product__code')

    def reorders(self):
        reorders = []
        for stockout in list(self.stockouts()) + self.low_supply():
            monthly_consumption = stockout.get_monthly_consumption()
            if monthly_consumption is None:
                reorders.append((stockout.sql_product.code, None))
            else:
                reorders.append(
                    (
                        stockout.sql_product.code,
                        int(monthly_consumption * Decimal(stockout.sql_location.location_type.overstock_threshold)
                            - stockout.stock_on_hand)
                    )
                )
        return reorders

    def _get_facilities_with_stock_category(self, category):
        return [
            stock_state
            for stock_state in self.stock_states().distinct('sql_product__code').order_by('sql_product__code')
            if stock_state.stock_category == category
        ]

    def low_supply(self):
        return self._get_facilities_with_stock_category('understock')

    def overstocked(self):
        return self._get_facilities_with_stock_category('overstock')

    def receipts(self):
        return [
            transaction
            for transaction in self.transactions
            if transaction.action == 'receipts' and transaction.quantity != 0
        ]


def can_receive_email(user, verified_number):
    return user.email and verified_number.backend_id and verified_number.backend_id == 'MOBILE_BACKEND_TWILIO'


@quickcache(['domain'])
def get_country_id(domain):
    from custom.ewsghana import ROOT_SITE_CODE
    return SQLLocation.objects.get(domain=domain, site_code=ROOT_SITE_CODE).location_id


def has_input_stock_permissions(couch_user, location, domain):
    if not couch_user.is_web_user():
        return False

    domain_membership = couch_user.get_domain_membership(domain)

    if not domain_membership:
        return False

    administrator_role_id = UserRole.by_domain_and_name(domain, 'Administrator')[0].get_id

    if domain_membership.role_id == administrator_role_id:
        return True

    try:
        location_id = EWSExtension.objects.get(user_id=couch_user.get_id, domain=domain).location_id
        if location_id == location.location_id:
            return True
    except EWSExtension.DoesNotExist:
        pass

    if not domain_membership.location_id:
        return False

    try:
        user_location = SQLLocation.objects.get(location_id=domain_membership.location_id)
    except SQLLocation.DoesNotExist:
        return False

    if not user_location.location_type.administrative:
        if user_location.location_id != location.location_id:
            return False
    else:
        parents = location.get_ancestors().values_list('location_id', flat=True)
        if user_location.location_id not in parents:
            return False
    return True


def first_item(items, f):
    for item in items:
        if f(item):
            return item

REPORT_MAPPING = {
    'dashboard_report': 'custom.ewsghana.reports.specific_reports.dashboard_report.DashboardReport',
    'stock_status': 'custom.ewsghana.reports.specific_reports.stock_status_report.StockStatus',
    'reporting_page': 'custom.ewsghana.reports.specific_reports.reporting_rates.ReportingRatesReport',
    'ews_mapreport': 'custom.ewsghana.reports.maps.EWSMapReport',
    'cms_rms_summary_report': 'custom.ewsghana.reports.email_reports.CMSRMSReport',
    'stock_summary_report': 'custom.ewsghana.reports.email_reports.StockSummaryReport'
}


def filter_slugs_by_role(couch_user, domain):
    slugs = [
        ['dashboard_report', 'Dashboard'],
        ['stock_status', 'Stock Status'],
        ['reporting_page', 'Reporting'],
        ['ews_mapreport', 'Maps'],
        ['stock_summary_report', 'Stock Summary'],
        ['cms_rms_summary_report', 'CMS and RMS Summary']
    ]
    if couch_user.is_domain_admin(domain) or couch_user.is_superuser:
        return slugs
    domain_membership = couch_user.get_domain_membership(domain)
    permissions = domain_membership.permissions
    if not permissions.view_reports:
        return [slug for slug in slugs if REPORT_MAPPING[slug[0]] in permissions.view_report_list]


def ews_date_format(date):
    return date.strftime("%b %d, %Y")

TEACHING_HOSPITAL_MAPPING = {
    'kath': {'parent_external_id': '319'},
    'kbth': {'parent_external_id': '2'},
}

TEACHING_HOSPITALS = ['kath', 'kbth', 'ccmh', 'trh']


def drange(start, stop, step):
    r = start
    while r < stop:
        yield r
        r += step


def get_products_for_locations(locations):
    return SQLProduct.objects.filter(
        pk__in=locations.values_list('_products', flat=True),
    ).exclude(is_archived=True)


def get_products_for_locations_by_program(locations, program):
    return SQLProduct.objects.filter(
        pk__in=locations.values_list('_products', flat=True),
        program_id=program
    ).exclude(is_archived=True)


def get_products_for_locations_by_products(locations, products):
    return SQLProduct.objects.filter(
        pk__in=locations.values_list('_products', flat=True),
    ).filter(pk__in=products).exclude(is_archived=True)


def get_supply_points(domain, location_id):
    supply_points = []
    if location_id:
        location = SQLLocation.objects.get(
            domain=domain,
            location_id=location_id
        )
        if location.location_type.name == 'country':
            supply_points = SQLLocation.objects.filter(
                Q(parent__location_id=location_id, is_archived=False) |
                Q(location_type__name='Regional Medical Store', domain=domain) |
                Q(location_type__name='Teaching Hospital', domain=domain)
            ).order_by('name').exclude(supply_point_id__isnull=True)
        else:
            supply_points = SQLLocation.objects.filter(
                parent__location_id=location_id, is_archived=False,
                location_type__administrative=False,
            ).order_by('name').exclude(supply_point_id__isnull=True)
    return supply_points


def report_status(sql_location, days_until_late=DAYS_UNTIL_LATE):
    commodities_stocked = sql_location.products
    latest_stocks = StockState.objects.filter(
        case_id=sql_location.supply_point_id, sql_product__in=commodities_stocked
    )

    if not latest_stocks:
        return [], commodities_stocked

    pks = [stock_state.sql_product.pk for stock_state in latest_stocks]
    missing_products = list(commodities_stocked.exclude(pk__in=pks))

    deadline = datetime.now() + relativedelta(days=-days_until_late)
    on_time_stocks = latest_stocks.filter(last_modified_date__gte=deadline)
    missing_stocks = [
        stock_state.sql_product for stock_state in latest_stocks.filter(last_modified_date__lt=deadline)
    ]
    return [stock_state.sql_product for stock_state in on_time_stocks], missing_products + missing_stocks


def send_sms(domain, recipient, phone_number, message):
    if isinstance(phone_number, VerifiedNumber):
        send_sms_to_verified_number(phone_number, message)
    else:
        core_send_sms(domain, recipient, phone_number, message)


def has_notifications_enabled(domain, web_user):
    try:
        return EWSExtension.objects.get(domain=domain, user_id=web_user.get_id).sms_notifications
    except EWSExtension.DoesNotExist:
        return False


def set_sms_notifications(domain, web_user, sms_notifications):
    try:
        extension = EWSExtension.objects.get(domain=domain, user_id=web_user.get_id)
        extension.sms_notifications = sms_notifications
        extension.save()
    except EWSExtension.DoesNotExist:
        EWSExtension.objects.create(domain=domain, user_id=web_user.get_id, sms_notifications=sms_notifications)
