from decimal import Decimal
from corehq import Domain
from corehq.apps.accounting import generator
from corehq.apps.accounting.models import BillingAccount, DefaultProductPlan, SoftwarePlanEdition, Subscription
from corehq.apps.commtrack.models import StockState, SupplyPointCase
from corehq.apps.locations.models import SQLLocation
from datetime import timedelta, datetime
from dateutil import rrule
from dateutil.rrule import MO
from django.utils import html
from corehq.apps.locations.schema import LocationType
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import add_msg_tags
from corehq.apps.sms.models import SMSLog, OUTGOING
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.models import EWSGhanaConfig

TEST_DOMAIN = 'ewsghana-receipts-test'


def get_supply_points(location_id, domain):
    loc = SQLLocation.objects.get(location_id=location_id)
    location_types = [loc_type.name for loc_type in filter(
        lambda loc_type: not loc_type.administrative,
        Domain.get_by_name(domain).location_types
    )]
    if loc.location_type == 'district':
        locations = SQLLocation.objects.filter(parent=loc)
    elif loc.location_type == 'region':
        locations = SQLLocation.objects.filter(parent__parent=loc)
    elif loc.location_type in location_types:
        locations = SQLLocation.objects.filter(id=loc.id)
    else:
        locations = SQLLocation.objects.filter(domain=domain, location_type__in=location_types)
    return locations.exclude(supply_point_id__isnull=True)


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


def calculate_last_period(enddate):
    last_th = enddate - timedelta(days=enddate.weekday()) + timedelta(days=3, weeks=-1)
    fr_before = last_th - timedelta(days=6)
    return fr_before, last_th


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
        return filter_relevant(SQLLocation.objects.filter(domain=domain))


def prepare_domain(domain_name):
    from corehq.apps.commtrack.tests import bootstrap_domain
    domain = bootstrap_domain(domain_name)
    domain.location_types = [
        LocationType(name="country", allowed_parents=[""],
                     administrative=True),
        LocationType(name="Central Medical Store", allowed_parents=["country"],
                     administrative=False),
        LocationType(name="Teaching Hospital", allowed_parents=["country"],
                     administrative=False),
        LocationType(name="region", allowed_parents=["country"],
                     administrative=True),
        LocationType(name="Regional Medical Store", allowed_parents=["region"],
                     administrative=False),
        LocationType(name="Regional Hospital", allowed_parents=["region"],
                     administrative=False),
        LocationType(name="district", allowed_parents=["region"],
                     administrative=True),
        LocationType(name="Clinic", allowed_parents=["district"],
                     administrative=False),
        LocationType(name="District Hospital", allowed_parents=["district"],
                     administrative=False),
        LocationType(name="Health Centre", allowed_parents=["district"],
                     administrative=False),
        LocationType(name="CHPS Facility", allowed_parents=["district"],
                     administrative=False),
        LocationType(name="Hospital", allowed_parents=["district"],
                     administrative=False),
        LocationType(name="Psychiatric Hospital", allowed_parents=["district"],
                     administrative=False),
        LocationType(name="Polyclinic", allowed_parents=["district"],
                     administrative=False),
        LocationType(name="facility", allowed_parents=["district"],
                     administrative=False)
    ]
    domain.save()
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
TEST_BACKEND = 'test-backend'


def bootstrap_user(username=TEST_USER, domain=TEST_DOMAIN,
                   phone_number=TEST_NUMBER, password=TEST_PASSWORD,
                   backend=TEST_BACKEND, first_name='', last_name='',
                   home_loc=None, user_data=None,
                   ):
    from corehq.apps.commtrack.helpers import make_supply_point

    user_data = user_data or {}
    user = CommCareUser.create(
        domain,
        username,
        password,
        phone_numbers=[TEST_NUMBER],
        user_data=user_data,
        first_name=first_name,
        last_name=last_name
    )

    if not SupplyPointCase.get_by_location(home_loc):
        make_supply_point(domain, home_loc)

    user.set_location(home_loc)

    user.save_verified_number(domain, phone_number, verified=True, backend_id=backend)
    return CommCareUser.wrap(user.to_json())

REORDER_LEVEL = Decimal("1.5")


class ProductsReportHelper(object):

    def __init__(self, location, transactions):
        self.location = location
        self.transactions = transactions

    def reported_products(self):
        return [SQLProduct.objects.get(product_id=transaction.product_id) for transaction in self.transactions]

    def missing_products(self):
        return set(self.location.products) - set(self.reported_products())

    def stock_states(self):
        product_ids = [product.product_id for product in self.reported_products()]
        return StockState.objects.filter(product_id__in=product_ids)

    def stockouts(self):
        return self.stock_states().filter(stock_on_hand=0).order_by('sql_product__code')

    def reorders(self):
        reorders = []
        for stockout in list(self.stockouts()) + self.low_supply():
            monthly_consumption = stockout.get_monthly_consumption()
            if monthly_consumption is None:
                reorders.append((stockout.sql_product.code, None))
            else:
                reorders.append((stockout.sql_product.code, int(monthly_consumption * REORDER_LEVEL)))
        return reorders

    def _get_facilities_with_stock_category(self, category):
        product_ids = [product.product_id for product in self.reported_products()]
        return [
            stock_state
            for stock_state in StockState.objects.filter(
                product_id__in=product_ids,
            ).order_by('sql_product__code')
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
            if transaction.action == 'receipts' and transaction.quantity != '0'
        ]
