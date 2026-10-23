from datetime import date
from uuid import uuid4

from django.test import override_settings

import pytest
from unmagic import fixture, use

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscriber,
    Subscription,
)
from corehq.apps.hqwebapp.chat_quota import UNLIMITED, get_chatbot_message_quota
from corehq.apps.users.models import DomainMembership, WebUser


def make_user(domains=(), username='chat@example.com'):
    return WebUser(
        username=username,
        domains=domains,
        domain_memberships=[DomainMembership(domain=domain) for domain in domains],
    )


def _subscribe(domain_name, edition, is_active=True):
    account = BillingAccount.get_or_create_account_by_domain(
        domain_name, created_by='test@example.com',
    )[0]
    subscriber, _ = Subscriber.objects.get_or_create(domain=domain_name)
    # SQL only — Subscription.save() would publish a Couch domain change.
    Subscription.visible_objects.bulk_create([Subscription(
        account=account,
        subscriber=subscriber,
        plan_version=DefaultProductPlan.get_default_plan_version(edition=edition),
        date_start=date.today(),
        is_active=is_active,
    )])
    Subscription._get_active_subscription_by_domain.clear(Subscription, domain_name)


@fixture
def domain_on_plan():
    """Return a domain name, optionally with an active subscription of the given edition."""
    domains = []

    def create(edition=None, is_active=True):
        domain = f'test-{uuid4().hex}'
        domains.append(domain)
        if edition is not None:
            _subscribe(domain, edition, is_active=is_active)
        return domain

    yield create
    for domain in domains:
        Subscription._get_active_subscription_by_domain.clear(Subscription, domain)


@pytest.mark.parametrize(('editions', 'expected'), [
    ([], 0),
    ([None], 0),
    ([SoftwarePlanEdition.FREE], 0),
    ([SoftwarePlanEdition.STANDARD], 30),
    ([SoftwarePlanEdition.PRO], 30),
    ([SoftwarePlanEdition.ADVANCED], 60),
    ([SoftwarePlanEdition.ENTERPRISE], 60),
    ([SoftwarePlanEdition.PAUSED], 0),
    ([SoftwarePlanEdition.STANDARD, SoftwarePlanEdition.PRO], 30),
    ([SoftwarePlanEdition.FREE, SoftwarePlanEdition.ADVANCED, SoftwarePlanEdition.PRO], 60),
])
@use('db', domain_on_plan)
@override_settings(ENTERPRISE_MODE=False)
def test_get_chatbot_message_quota(editions, expected):
    domains = [domain_on_plan()(edition) for edition in editions]
    assert get_chatbot_message_quota(make_user(domains)) == expected


@override_settings(ENTERPRISE_MODE=False)
def test_staff_is_unlimited_without_database_access():
    assert get_chatbot_message_quota(make_user(['domain'], username='chat@dimagi.com')) == UNLIMITED


@use('db', domain_on_plan)
@override_settings(ENTERPRISE_MODE=False)
def test_inactive_subscription_has_no_allowance():
    domain = domain_on_plan()(SoftwarePlanEdition.ADVANCED, is_active=False)
    assert get_chatbot_message_quota(make_user([domain])) == 0
