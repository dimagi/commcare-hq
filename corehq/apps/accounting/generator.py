from __future__ import unicode_literals, absolute_import, print_function
import random

from dimagi.utils.data import generator
from corehq.apps.accounting.models import *
from corehq.apps.users.models import WebUser

# don't actually use this for initializing new plans! the amounts have been changed to make it easier on testing:
COMMCARE_PLANS = [
    {
        'name': "CommCare Community",
        'fee': Decimal('0.0'),
        'rates': [
            {
                'name': "User Community",
                'limit': 2,
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


def instantiate_plans(plan_list=None):
    plan_list = plan_list or COMMCARE_PLANS
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


def delete_all_plans():
    SoftwarePlanVersion.objects.all().delete()
    SoftwarePlan.objects.all().delete()

    SoftwareProductRate.objects.all().delete()
    SoftwareProduct.objects.all().delete()

    FeatureRate.objects.all().delete()
    Feature.objects.all().delete()


def arbitrary_subscribable_plan():
    subscribable_plans = [plan['name'] for plan in COMMCARE_PLANS if plan['name'] != "CommCare Community"]
    return SoftwarePlan.objects.get(name=random.choice(subscribable_plans))
