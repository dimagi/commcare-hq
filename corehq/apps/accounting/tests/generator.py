import calendar
import datetime
import random
import uuid
from decimal import Decimal

from django.apps import apps
from django.conf import settings
from django.core.management import call_command

from unittest import mock
from nose.tools import nottest

from dimagi.utils.data import generator as data_gen

from corehq.apps.accounting.bootstrap.config.testing import (
    BOOTSTRAP_CONFIG_TESTING,
)
from corehq.apps.accounting.bootstrap.utils import ensure_plans
from corehq.apps.accounting.models import (
    BillingAccount,
    BillingContactInfo,
    Currency,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscriber,
    Subscription,
    SubscriptionType,
)
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.util.test_utils import unit_testing_only


def bootstrap_accounting():
    from ..bootstrap.config.enterprise import BOOTSTRAP_CONFIG as enterprise_config
    from ..bootstrap.config.report_builder_v0 import BOOTSTRAP_CONFIG as report_builder_config
    from ..bootstrap.config.resellers_and_managed_hosting import BOOTSTRAP_CONFIG as resellers_config
    from ..bootstrap.config.user_buckets_jan_2017 import BOOTSTRAP_CONFIG as self_service_config
    from ..bootstrap.config.new_plans_dec_2019 import BOOTSTRAP_CONFIG as new_plans_dec_2019
    call_command('cchq_prbac_bootstrap')
    pricing_config = self_service_config
    pricing_config.update(enterprise_config)
    pricing_config.update(report_builder_config)
    pricing_config.update(resellers_config)
    pricing_config.update(new_plans_dec_2019)
    ensure_plans(pricing_config, verbose=True, apps=apps)


@unit_testing_only
@nottest
def bootstrap_test_software_plan_versions():
    ensure_plans(BOOTSTRAP_CONFIG_TESTING, verbose=False, apps=apps)


@unit_testing_only
def init_default_currency():
    currency, _ = Currency.objects.get_or_create(
        code=settings.DEFAULT_CURRENCY
    )
    currency.name = "Default Currency"
    currency.rate_to_default = Decimal('1.0')
    currency.symbol = settings.DEFAULT_CURRENCY_SYMBOL
    currency.save()
    return currency


@unit_testing_only
def unique_name():
    return uuid.uuid4().hex.lower()[:60]


@unit_testing_only
def create_arbitrary_web_user_name(is_dimagi=False):
    return "%s@%s.com" % (unique_name(), 'dimagi' if is_dimagi else 'gmail')


def billing_account(web_user_creator, web_user_contact, is_customer_account=False):
    account_name = data_gen.arbitrary_unique_name(prefix="BA")[:40]
    currency = Currency.objects.get(code=settings.DEFAULT_CURRENCY)
    billing_account = BillingAccount.objects.create(
        name=account_name,
        created_by=web_user_creator,
        currency=currency,
    )
    arbitrary_contact_info(billing_account, web_user_contact)
    if is_customer_account:
        billing_account.is_customer_billing_account = True
        billing_account.save()
    return billing_account


@unit_testing_only
def arbitrary_contact_info(account, web_user_creator):
    return BillingContactInfo.objects.create(
        account=account,
        first_name=data_gen.arbitrary_firstname(),
        last_name=data_gen.arbitrary_lastname(),
        email_list=[web_user_creator],
        phone_number="+15555555",
        company_name="Company Name",
        first_line="585 Mass Ave",
        city="Cambridge",
        state_province_region="MA",
        postal_code="02139",
        country="US",
    )


@unit_testing_only
def subscribable_plan_version(edition=SoftwarePlanEdition.STANDARD):
    return DefaultProductPlan.get_default_plan_version(edition)


@unit_testing_only
def generate_domain_subscription(account, domain, date_start, date_end,
                                 plan_version=None, service_type=SubscriptionType.NOT_SET,
                                 is_active=False, do_not_invoice=False):
    subscriber, _ = Subscriber.objects.get_or_create(domain=domain.name)
    subscription = Subscription(
        account=account,
        plan_version=plan_version or subscribable_plan_version(),
        subscriber=subscriber,
        date_start=date_start,
        date_end=date_end,
        service_type=service_type,
        is_active=is_active,
        do_not_invoice=do_not_invoice
    )
    subscription.save()
    return subscription


@unit_testing_only
def get_start_date():
    start_date = datetime.date.today()
    (_, last_day) = calendar.monthrange(start_date.year, start_date.month)
    # make sure that the start_date does not fall on the first or last day of the month:
    return start_date.replace(day=min(max(2, start_date.day), last_day - 1))


@unit_testing_only
def arbitrary_domain():
    domain = Domain(
        name=data_gen.arbitrary_unique_name()[:20],
        is_active=True,
    )
    domain.save()
    return domain


@unit_testing_only
def arbitrary_domain_and_subscriber():
    domain = arbitrary_domain()
    subscriber, _ = Subscriber.objects.get_or_create(domain=domain.name)
    return domain, subscriber


@unit_testing_only
def arbitrary_user(domain_name, is_active=True, is_webuser=False):
    username = unique_name()
    if is_webuser:
        username = create_arbitrary_web_user_name()
        user_cls = WebUser
        email = username
    else:
        username = unique_name()
        user_cls = CommCareUser
        email = None
    commcare_user = user_cls.create(domain_name, username, 'test123', None, None, email)
    commcare_user.is_active = is_active
    return commcare_user


@unit_testing_only
def arbitrary_commcare_users_for_domain(domain, num_users, is_active=True):
    CommCareUser.bulk_save([
        arbitrary_user(domain, is_active=is_active)
        for _ in range(0, num_users)
    ])
    return num_users


@unit_testing_only
def arbitrary_webusers_for_domain(domain, num_users, is_active=True):
    WebUser.bulk_save([
        arbitrary_user(domain, is_active=is_active, is_webuser=True)
        for _ in range(0, num_users)
    ])
    return num_users


@unit_testing_only
def create_excess_community_users(domain):
    community_plan_version = DefaultProductPlan.get_default_plan_version()
    num_active_users = random.randint(community_plan_version.user_limit + 1,
                                      community_plan_version.user_limit + 4)
    arbitrary_commcare_users_for_domain(domain.name, num_active_users)
    return num_active_users


class FakeStripeCard(mock.MagicMock):

    def __init__(self):
        super(FakeStripeCard, self).__init__()
        self._metadata = {}
        self.last4 = '1234'
        self.id = uuid.uuid4().hex.lower()[:15]

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, value):
        """Stripe returns everything as JSON. This will do for testing"""
        self._metadata = {k: str(v) for k, v in value.items()}

    def save(self):
        pass


class FakeStripeCustomer(mock.MagicMock):

    def __init__(self, cards):
        super(FakeStripeCustomer, self).__init__()
        self.id = uuid.uuid4().hex.lower()[:25]
        self.cards = mock.MagicMock()
        self.cards.data = cards


class FakeStripeCardManager:
    _cards = {}

    @classmethod
    def create_card(cls):
        card = FakeStripeCard()
        cls._cards[card.id] = card
        return card

    @classmethod
    def get_card_by_id(cls, card_id):
        return cls._cards.get(card_id)


class FakeStripeCustomerManager:
    _customers = {}

    @classmethod
    def create_customer(cls, cards):
        customer = FakeStripeCustomer(cards)
        cls._customers[customer.id] = customer
        return customer

    @classmethod
    def get_customer_by_id(cls, customer_id):
        return cls._customers.get(customer_id)
