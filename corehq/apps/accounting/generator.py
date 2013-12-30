from __future__ import unicode_literals, absolute_import, print_function
import calendar
from decimal import Decimal
import random
import datetime

from django.conf import settings

from dimagi.utils.dates import add_months
from dimagi.utils.data import generator as data_gen

from corehq.apps.accounting.models import (FeatureType, Currency, BillingAccount, FeatureRate, SoftwarePlanVersion,
                                           SoftwarePlan, SoftwareProductRate, Subscription, Subscriber, SoftwareProduct,
                                           Feature, SoftwareProductType, DefaultProductPlan)
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser, CommCareUser

# don't actually use the plan lists below for initializing new plans! the amounts have been changed to make
# it easier for testing:
MAX_COMMUNITY_USERS = 2

COMMUNITY_COMMCARE_PLANS = [
    {
        'name': "CommCare Community",
        'product_type': SoftwareProductType.COMMCARE,
        'fee': Decimal('0.0'),
        'rates': [
            {
                'name': "User Community",
                'limit': MAX_COMMUNITY_USERS,
                'excess': Decimal('1.00'),
                'type': FeatureType.USER,
            },
            {
                'name': "SMS Community",
                'type': FeatureType.SMS,
            },
        ],
    },
    {
        'name': "CommTrack Community",
        'product_type': SoftwareProductType.COMMTRACK,
        'fee': Decimal('0.0'),
        'rates': [
            {
                'name': "User CommTrack Community",
                'limit': MAX_COMMUNITY_USERS,
                'excess': Decimal('1.00'),
                'type': FeatureType.USER,
            },
            {
                'name': "SMS CommTrack Community",
                'type': FeatureType.SMS,
            },
        ],
    },
    {
        'name': "CommConnect Community",
        'product_type': SoftwareProductType.COMMCONNECT,
        'fee': Decimal('0.0'),
        'rates': [
            {
                'name': "User CommConnect Community",
                'limit': MAX_COMMUNITY_USERS,
                'excess': Decimal('1.00'),
                'type': FeatureType.USER,
            },
            {
                'name': "SMS CommConnect Community",
                'type': FeatureType.SMS,
            },
        ],
    },
]

SUBSCRIBABLE_COMMCARE_PLANS = [
    {
        'name': "CommCare Standard",
        'fee': Decimal('100.00'),
        'rates': [
            {
                'name': "User Standard",
                'limit': 4,
                'excess': Decimal('1.00'),
                'type': FeatureType.USER,
            },
            {
                'name': "SMS Standard",
                'limit': 10,
                'type': FeatureType.SMS,
            },
        ],
    },
    {
        'name': "CommCare Pro",
        'fee': Decimal('500.00'),
        'rates': [
            {
                'name': "User Pro",
                'limit': 6,
                'excess': Decimal('1.00'),
                'type': FeatureType.USER,
            },
            {
                'name': "SMS Pro",
                'limit': 16,
                'type': FeatureType.SMS,
            },
        ],
    },
    {
        'name': "CommCare Advanced",
        'fee': Decimal('1000.00'),
        'rates': [
            {
                'name': "User Advanced",
                'limit': 8,
                'excess': Decimal('1.00'),
                'type': FeatureType.USER,
            },
            {
                'name': "SMS Advanced",
                'limit': 20,
                'type': FeatureType.SMS,
            },
        ],
    },
]


def init_default_currency():
    currency, _ = Currency.objects.get_or_create(
        code=settings.DEFAULT_CURRENCY,
        name="Default Currency",
        rate_to_default=Decimal('1.0'),
        symbol=settings.DEFAULT_CURRENCY_SYMBOL,
    )
    return currency


def arbitrary_web_user(save=True, is_dimagi=False):
    domain = data_gen.arbitrary_unique_name().lower()[:25]
    username = "%s@%s.com" % (data_gen.arbitrary_username(), 'dimagi' if is_dimagi else 'gmail')
    web_user = WebUser.create(domain, username, 'test123')
    if save:
        web_user.save()
    return web_user


def billing_account(web_user_creator, web_user_contact, currency=None, save=True):
    account_name = data_gen.arbitrary_unique_name(prefix="BA")[:40]
    currency = currency or Currency.objects.get(code=settings.DEFAULT_CURRENCY)
    billing_account = BillingAccount(
        name=account_name,
        created_by=web_user_creator.username,
        web_user_contact=web_user_contact.username,
        currency=currency,
    )
    if save:
        billing_account.save()

    return billing_account


def delete_all_accounts():
    BillingAccount.objects.all().delete()
    Currency.objects.all().delete()


def _instantiate_plans_from_list(plan_list):
    plans = []
    for plan in plan_list:
        software_plan, created = SoftwarePlan.objects.get_or_create(name=plan['name'])
        plan_version = SoftwarePlanVersion(plan=software_plan)
        plan_version.save()
        plan_version.product_rates.add(SoftwareProductRate.new_rate(plan['name'], plan['fee']))
        for rate in plan['rates']:
            plan_version.feature_rates.add(
                FeatureRate.new_rate(
                    rate['name'],
                    rate['type'],
                    monthly_fee=rate.get('fee'),
                    monthly_limit=rate.get('limit'),
                    per_excess_fee=rate.get('excess'),
                )
            )
        plan_version.save()
        plans.append(software_plan)
    return plans


def instantiate_subscribable_plans(plan_list=None):
    _instantiate_plans_from_list(SUBSCRIBABLE_COMMCARE_PLANS)


def instantiate_community_plans():
    plans = _instantiate_plans_from_list(COMMUNITY_COMMCARE_PLANS)
    for ind, plan in enumerate(plans):
        DefaultProductPlan.objects.get_or_create(
            product_type=COMMUNITY_COMMCARE_PLANS[ind]['product_type'],
            plan=plan,
        )


def delete_all_plans():
    DefaultProductPlan.objects.all().delete()
    SoftwarePlanVersion.objects.all().delete()
    SoftwarePlan.objects.all().delete()

    SoftwareProductRate.objects.all().delete()
    SoftwareProduct.objects.all().delete()

    FeatureRate.objects.all().delete()
    Feature.objects.all().delete()


def arbitrary_subscribable_plan():
    subscribable_plans = [plan['name'] for plan in SUBSCRIBABLE_COMMCARE_PLANS]
    plan = SoftwarePlan.objects.get(name=random.choice(subscribable_plans))
    return plan.softwareplanversion_set.latest('date_created')


def generate_domain_subscription_from_date(date_start, billing_account, domain,
                                           num_months=None, is_immediately_active=False,
                                           delay_invoicing_until=None, save=True):
    # make sure the first month is never a full month (for testing)
    date_start = date_start.replace(day=max(2, date_start.day))

    subscription_length = num_months or random.randint(3, 25)
    date_end_year, date_end_month = add_months(date_start.year, date_start.month, subscription_length)
    date_end_last_day = calendar.monthrange(date_end_year, date_end_month)[1]

    # make sure that the last month is never a full month (for testing)
    date_end = datetime.date(date_end_year, date_end_month, min(date_end_last_day - 1, date_start.day + 1))

    subscriber, _ = Subscriber.objects.get_or_create(domain=domain, organization=None)
    subscription = Subscription(
        account=billing_account,
        plan=arbitrary_subscribable_plan(),
        subscriber=subscriber,
        salesforce_contract_id=data_gen.arbitrary_unique_name("SFC")[:80],
        date_start=date_start,
        date_end=date_end,
        is_active=is_immediately_active,
        date_delay_invoicing=delay_invoicing_until,
    )
    if save:
        subscription.save()
    return subscription, subscription_length


def delete_all_subscriptions():
    Subscription.objects.all().delete()
    Subscriber.objects.all().delete()


def get_start_date():
    start_date = datetime.date.today()
    (_, last_day) = calendar.monthrange(start_date.year, start_date.month)
    # make sure that the start_date does not fall on the first or last day of the month:
    return start_date.replace(day=min(max(2, start_date.day), last_day-1))


def arbitrary_domain():
    domain = Domain(
        name=data_gen.arbitrary_unique_name()[:20],
        is_active=True,
    )
    domain.save()
    return domain


def arbitrary_commcare_users_for_domain(domain, num_users, is_active=True):
    count = 0
    for _ in range(0, num_users):
        count += 1
        username = data_gen.arbitrary_unique_name()[:80]
        commcare_user = CommCareUser.create(domain, username, 'test123')
        commcare_user.is_active = is_active
        commcare_user.save()
    return num_users


def arbitrary_sms_billables_for_domain(domain, direction, message_month_date, num_sms):
    from corehq.apps.smsbillables.models import SmsBillable, SmsGatewayFee, SmsUsageFee
    from corehq.apps.smsbillables import generator as sms_gen

    gateway_fee = SmsGatewayFee.create_new('MACH', direction, sms_gen.arbitrary_fee())
    usage_fee = SmsUsageFee.create_new(direction, sms_gen.arbitrary_fee())

    _, last_day_message = calendar.monthrange(message_month_date.year, message_month_date.month)

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
        )
        sms_billable.save()
