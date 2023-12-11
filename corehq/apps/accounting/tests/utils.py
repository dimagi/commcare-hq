from datetime import date

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    Subscription,
    SubscriptionAdjustment,
)
from corehq.apps.accounting.tests import generator
import stripe
from contextlib import contextmanager
from unittest import mock
from corehq.apps.accounting.tests.generator import (
    FakeStripeCardManager,
    FakeStripeCustomerManager,
)


class DomainSubscriptionMixin(object):
    """
    util for setting up a subscription for domain
    """

    __subscriptions = None
    __accounts = None

    @classmethod
    def setup_subscription(cls, domain_name, software_plan):
        generator.bootstrap_test_software_plan_versions()

        plan = DefaultProductPlan.get_default_plan_version(edition=software_plan)
        account = BillingAccount.get_or_create_account_by_domain(
            domain_name, created_by="automated-test" + cls.__name__
        )[0]

        current_subscription = Subscription.get_active_subscription_by_domain(domain_name)
        if current_subscription:
            current_subscription.date_end = date.today()
            current_subscription.is_active = False
            current_subscription.save()

        subscription = Subscription.new_domain_subscription(account, domain_name, plan)
        subscription.is_active = True
        subscription.save()
        cls.__subscriptions = cls.__subscriptions or {}
        cls.__subscriptions[domain_name] = subscription
        cls.__accounts = cls.__accounts or {}
        cls.__accounts[domain_name] = account

    @classmethod
    def teardown_subscriptions(cls):
        for domain in cls.__subscriptions:
            cls.teardown_subscription(domain)

    @classmethod
    def teardown_subscription(cls, domain):
        try:
            SubscriptionAdjustment.objects.all().delete()
            Subscription.visible_and_suppressed_objects.all().delete()
            cls.__subscriptions[domain].delete()
            cls.__accounts[domain].delete()
        finally:
            Subscription._get_active_subscription_by_domain.clear(Subscription, domain)


@contextmanager
def mocked_stripe_api():
    with mock.patch.object(stripe.Customer, 'modify_source') as mock_modify_source, \
         mock.patch.object(stripe.Customer, 'list_sources') as mock_list_sources:
        setup_stripe_common_mocks(mock_list_sources, mock_modify_source)
        yield


def setup_stripe_common_mocks(mock_list_sources, mock_modify_source):
    def modify_source_side_effect(*args, **kwargs):
        updated_metadata = {k: str(v) for k, v in kwargs['metadata'].items()}
        FakeStripeCardManager.get_card_by_id(kwargs['id']).metadata.update(updated_metadata)

    def list_sources_side_effect(*args, **kwargs):
        return FakeStripeCustomerManager.get_customer_by_id(kwargs['customer']).cards

    mock_modify_source.side_effect = modify_source_side_effect
    mock_list_sources.side_effect = list_sources_side_effect
