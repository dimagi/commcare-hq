from __future__ import unicode_literals, absolute_import, print_function

from dimagi.utils.data import generator
from corehq.apps.accounting.models import *
from corehq.apps.users.models import WebUser


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

