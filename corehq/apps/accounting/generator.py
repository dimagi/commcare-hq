from __future__ import unicode_literals, absolute_import, print_function
import calendar
from decimal import Decimal
import random
import datetime
import uuid
import mock

from django.conf import settings
from django.core.management import call_command

from dimagi.utils.data import generator as data_gen

from corehq.apps.accounting.models import (
    BillingAccount,
    BillingContactInfo,
    Currency,
    DefaultProductPlan,
    Feature,
    FeatureRate,
    SoftwarePlan,
    SoftwarePlanEdition,
    SoftwareProductType,
    Subscriber,
    Subscription,
    SubscriptionAdjustment,
    SubscriptionType,
    SoftwarePlanVersion,
    SoftwareProduct,
    SoftwareProductRate,
)
from corehq.apps.domain.models import Domain
from corehq.apps.smsbillables.generator import DIRECTIONS
from corehq.apps.smsbillables.models import (
    SmsBillable,
    SmsGatewayFee,
    SmsGatewayFeeCriteria,
    SmsUsageFee,
    SmsUsageFeeCriteria,
)
from corehq.apps.users.models import WebUser, CommCareUser


def instantiate_accounting_for_tests():
    call_command('cchq_prbac_bootstrap', testing=True)

    DefaultProductPlan.objects.all().delete()
    SoftwarePlanVersion.objects.all().delete()
    SoftwarePlan.objects.all().delete()
    SoftwareProductRate.objects.all().delete()
    SoftwareProduct.objects.all().delete()
    FeatureRate.objects.all().delete()
    Feature.objects.all().delete()
    call_command('cchq_software_plan_bootstrap', testing=True)


def init_default_currency():
    currency, _ = Currency.objects.get_or_create(
        code=settings.DEFAULT_CURRENCY
    )
    currency.name = "Default Currency"
    currency.rate_to_default = Decimal('1.0')
    currency.symbol = settings.DEFAULT_CURRENCY_SYMBOL
    currency.save()
    return currency


def unique_name():
    return uuid.uuid4().hex.lower()[:60]


def arbitrary_web_user(save=True, is_dimagi=False):
    domain = Domain(name=unique_name()[:25])
    domain.save()
    username = "%s@%s.com" % (unique_name(), 'dimagi' if is_dimagi else 'gmail')
    try:
        web_user = WebUser.create(domain.name, username, 'test123')
    except Exception:
        web_user = WebUser.get_by_username(username)
    web_user.is_active = True
    if save:
        web_user.save()
    return web_user


def billing_account(web_user_creator, web_user_contact, currency=None, save=True):
    account_name = data_gen.arbitrary_unique_name(prefix="BA")[:40]
    currency = currency or Currency.objects.get(code=settings.DEFAULT_CURRENCY)
    billing_account = BillingAccount(
        name=account_name,
        created_by=web_user_creator.username,
        currency=currency,
    )
    if save:
        billing_account.save()
        billing_contact = arbitrary_contact_info(billing_account, web_user_contact)
        billing_contact.save()
    return billing_account


def arbitrary_contact_info(account, web_user_creator):
    return BillingContactInfo(
        account=account,
        first_name=data_gen.arbitrary_firstname(),
        last_name=data_gen.arbitrary_lastname(),
        email_list=[web_user_creator.username],
        phone_number="+15555555",
        company_name="Company Name",
        first_line="585 Mass Ave",
        city="Cambridge",
        state_province_region="MA",
        postal_code="02139",
        country="US",
    )


def delete_all_accounts():
    BillingContactInfo.objects.all().delete()
    BillingAccount.objects.all().delete()
    SmsBillable.objects.all().delete()
    SmsGatewayFee.objects.all().delete()
    SmsGatewayFeeCriteria.objects.all().delete()
    SmsUsageFee.objects.all().delete()
    SmsUsageFeeCriteria.objects.all().delete()
    Currency.objects.all().delete()


def subscribable_plan(edition=SoftwarePlanEdition.STANDARD):
    return DefaultProductPlan.objects.get(
        edition=edition,
        product_type=SoftwareProductType.COMMCARE,
        is_trial=False
    ).plan.get_version()


def generate_domain_subscription(account, domain, date_start, date_end,
                                 plan_version=None, service_type=SubscriptionType.NOT_SET):
    subscriber, _ = Subscriber.objects.get_or_create(domain=domain.name)
    subscription = Subscription(
        account=account,
        plan_version=plan_version or subscribable_plan(),
        subscriber=subscriber,
        date_start=date_start,
        date_end=date_end,
        service_type=service_type,
    )
    subscription.save()
    return subscription


def delete_all_subscriptions():
    SubscriptionAdjustment.objects.all().delete()
    Subscription.objects.all().delete()
    Subscriber.objects.all().delete()


def get_start_date():
    start_date = datetime.date.today()
    (_, last_day) = calendar.monthrange(start_date.year, start_date.month)
    # make sure that the start_date does not fall on the first or last day of the month:
    return start_date.replace(day=min(max(2, start_date.day), last_day - 1))


def arbitrary_domain():
    domain = Domain(
        name=data_gen.arbitrary_unique_name()[:20],
        is_active=True,
    )
    domain.save()
    return domain


def arbitrary_commcare_user(domain, is_active=True):
    username = unique_name()
    try:
        commcare_user = CommCareUser.create(domain, username, 'test123')
        commcare_user.is_active = is_active
        commcare_user.save()
        return commcare_user
    except Exception:
        pass


def arbitrary_commcare_users_for_domain(domain, num_users, is_active=True):
    count = 0
    for _ in range(0, num_users):
        count += 1
        commcare_user = None
        while commcare_user is None:
            commcare_user = arbitrary_commcare_user(domain, is_active=is_active)
    return num_users


def arbitrary_sms_billables_for_domain(domain, message_month_date, num_sms, direction=None, multipart_count=1):
    from corehq.apps.smsbillables.models import SmsBillable, SmsGatewayFee, SmsUsageFee

    direction = direction or random.choice(DIRECTIONS)

    gateway_fee = SmsGatewayFee.create_new('MACH', direction, Decimal(0.5))
    usage_fee = SmsUsageFee.create_new(direction, Decimal(0.25))

    _, last_day_message = calendar.monthrange(message_month_date.year, message_month_date.month)

    billables = []
    for _ in range(0, num_sms):
        sms_billable = SmsBillable(
            gateway_fee=gateway_fee,
            usage_fee=usage_fee,
            log_id=data_gen.arbitrary_unique_name()[:50],
            phone_number=data_gen.random_phonenumber(),
            domain=domain,
            direction=direction,
            date_sent=datetime.date(message_month_date.year, message_month_date.month,
                                    random.randint(1, last_day_message)),
            multipart_count=multipart_count,
        )
        sms_billable.save()
        billables.append(sms_billable)
    return billables


def create_excess_community_users(domain):
    community_plan = DefaultProductPlan.objects.get(
        product_type=SoftwareProductType.COMMCARE,
        edition=SoftwarePlanEdition.COMMUNITY
    ).plan.get_version()
    num_active_users = random.randint(community_plan.user_limit + 1,
                                      community_plan.user_limit + 4)
    arbitrary_commcare_users_for_domain(domain.name, num_active_users)
    return num_active_users


class FakeStripeCard(mock.MagicMock):

    def __init__(self):
        super(FakeStripeCard, self).__init__()
        self._metadata = {}
        self.last4 = '1234'

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, value):
        """Stripe returns everything as JSON. This will do for testing"""
        self._metadata = {k: str(v) for k, v in value.iteritems()}

    def save(self):
        pass


class FakeStripeCustomer(mock.MagicMock):

    def __init__(self, cards):
        super(FakeStripeCustomer, self).__init__()
        self.id = uuid.uuid4().hex.lower()[:25]
        self.cards = mock.MagicMock()
        self.cards.data = cards
