import datetime
from django.db import models

from corehq.apps.accounting import generator, tasks
from corehq.apps.accounting.models import BillingAccount, Currency, Subscription
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest


class TestBillingAccount(BaseAccountingTest):

    def setUp(self):
        super(TestBillingAccount, self).setUp()
        self.billing_contact = generator.arbitrary_web_user()
        self.dimagi_user = generator.arbitrary_web_user(is_dimagi=True)
        self.currency = generator.init_default_currency()
        self.billing_account = generator.billing_account(self.dimagi_user, self.billing_contact)

    def test_creation(self):
        self.assertIsNotNone(self.billing_account)

    def test_deletions(self):
        self.assertRaises(models.ProtectedError, self.currency.delete)

    def tearDown(self):
        self.billing_contact.delete()
        self.dimagi_user.delete()
        BillingAccount.objects.all().delete()
        Currency.objects.all().delete()


class TestSubscription(BaseAccountingTest):

    def setUp(self):
        super(TestSubscription, self).setUp()
        self.billing_contact = generator.arbitrary_web_user()
        self.dimagi_user = generator.arbitrary_web_user(is_dimagi=True)
        self.currency = generator.init_default_currency()
        self.account = generator.billing_account(self.dimagi_user, self.billing_contact)
        self.subscription, self.subscription_length = generator.generate_domain_subscription_from_date(
            datetime.date.today(), self.account, 'test'
        )

    def test_creation(self):
        self.assertIsNotNone(self.subscription)

    def test_no_activation(self):
        tasks.activate_subscriptions(based_on_date=self.subscription.date_start - datetime.timedelta(30))
        subscription = Subscription.objects.get(id=self.subscription.id)
        self.assertFalse(subscription.is_active)

    def test_activation(self):
        tasks.activate_subscriptions(based_on_date=self.subscription.date_start)
        subscription = Subscription.objects.get(id=self.subscription.id)
        self.assertTrue(subscription.is_active)

    def test_no_deactivation(self):
        tasks.activate_subscriptions(based_on_date=self.subscription.date_start)
        tasks.deactivate_subscriptions(based_on_date=self.subscription.date_end - datetime.timedelta(30))
        subscription = Subscription.objects.get(id=self.subscription.id)
        self.assertTrue(subscription.is_active)

    def test_deactivation(self):
        tasks.deactivate_subscriptions(based_on_date=self.subscription.date_end)
        subscription = Subscription.objects.get(id=self.subscription.id)
        self.assertFalse(subscription.is_active)

    def test_deletions(self):
        self.assertRaises(models.ProtectedError, self.account.delete)
        self.assertRaises(models.ProtectedError, self.subscription.plan_version.delete)
        self.assertRaises(models.ProtectedError, self.subscription.subscriber.delete)

    def tearDown(self):
        self.billing_contact.delete()
        self.dimagi_user.delete()

        generator.delete_all_subscriptions()
        generator.delete_all_accounts()
