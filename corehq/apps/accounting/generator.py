from __future__ import unicode_literals, absolute_import, print_function

from dimagi.utils.data import generator
from corehq.apps.accounting.models import *
from corehq.apps.users.models import WebUser

COMMCARE_PLANS = [
    {
        'name': "CommCare Community",
        'fee': 0.0,
        'rates': [
            {
                'name': "User Community",
                'limit': 50,
                'excess': 1.00,
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
        'fee': 100.00,
        'rates': [
            {
                'name': "User Standard",
                'limit': 100,
                'excess': 1.00,
                'type': FeatureType.USER,
            },
            {
                'name': "SMS Standard",
                'limit': 250,
                'type': FeatureType.SMS,
            },
        ],
    },
    {
        'name': "CommCare Pro",
        'fee': 500.00,
        'rates': [
            {
                'name': "User Pro",
                'limit': 500,
                'excess': 1.00,
                'type': FeatureType.USER,
            },
            {
                'name': "SMS Pro",
                'limit': 1000,
                'type': FeatureType.SMS,
            },
        ],
    },
    {
        'name': "CommCare Advanced",
        'fee': 1000.00,
        'rates': [
            {
                'name': "User Advanced",
                'limit': 1000,
                'excess': 1.00,
                'type': FeatureType.USER,
            },
            {
                'name': "SMS Advanced",
                'limit': 2000,
                'type': FeatureType.SMS,
            },
        ],
    },
]


def currency_usd():
    currency, _ = Currency.objects.get_or_create(code="USD", name="US Dollar")
    return currency


def arbitrary_web_user(save=True):
    domain = generator.arbitrary_unique_name().lower()
    username = generator.arbitrary_unique_name()

    web_user = WebUser.create(domain, username, 'test123')

    if save:
        web_user.save()

    return web_user


def billing_account(web_user_creator, web_user_contact, currency=None, save=True):
    account_name = generator.arbitrary_unique_name(prefix="BA")[:40]

    currency = currency or Currency.objects.get(code="USD")

    billing_account = BillingAccount(
        name=account_name,
        created_by=web_user_creator.username,
        web_user_contact=web_user_contact.username,
        currency=currency,
    )

    if save:
        billing_account.save()

    return billing_account


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
