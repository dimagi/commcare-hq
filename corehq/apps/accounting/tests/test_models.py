import datetime
from decimal import Decimal
from django.db import models
from corehq.apps.domain.models import Domain

from corehq.apps.accounting import generator, tasks
from corehq.apps.accounting.models import (
    BillingAccount,
    Currency,
    Subscription,
    SubscriptionType,
    BillingRecord,
    Invoice,
    SMALL_INVOICE_THRESHOLD,
)
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.utils import get_previous_month_date_range


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
        super(TestBillingAccount, self).tearDown()


class TestSubscription(BaseAccountingTest):

    def setUp(self):
        super(TestSubscription, self).setUp()
        self.billing_contact = generator.arbitrary_web_user()
        self.dimagi_user = generator.arbitrary_web_user(is_dimagi=True)
        self.domain = Domain(name='test')
        self.domain.save()
        self.currency = generator.init_default_currency()
        self.account = generator.billing_account(self.dimagi_user, self.billing_contact)
        self.subscription, self.subscription_length = generator.generate_domain_subscription_from_date(
            datetime.date.today(), self.account, self.domain.name
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
        self.domain.delete()

        generator.delete_all_subscriptions()
        generator.delete_all_accounts()
        super(TestSubscription, self).tearDown()


class TestBillingRecord(BaseAccountingTest):

    def setUp(self):
        super(TestBillingRecord, self).setUp()
        self.billing_contact = generator.arbitrary_web_user()
        self.dimagi_user = generator.arbitrary_web_user(is_dimagi=True)
        self.domain = Domain(name='test')
        self.domain.save()
        self.invoice_start, self.invoice_end = get_previous_month_date_range()
        self.currency = generator.init_default_currency()
        self.account = generator.billing_account(self.dimagi_user, self.billing_contact)
        self.subscription, self.subscription_length = generator.generate_domain_subscription_from_date(
            datetime.date.today(), self.account, self.domain.name
        )
        self.invoice = Invoice(
            subscription=self.subscription,
            date_start=self.invoice_start,
            date_end=self.invoice_end,
            is_hidden=False,
        )
        self.billing_record = BillingRecord(invoice=self.invoice)

    def test_should_send_email(self):
        self.assertTrue(self.billing_record.should_send_email)

    def test_should_send_email_contracted(self):
        self.subscription.service_type = SubscriptionType.CONTRACTED
        self.assertFalse(self.billing_record.should_send_email)

        self.invoice.balance = Decimal(SMALL_INVOICE_THRESHOLD - 1)
        self.assertFalse(self.billing_record.should_send_email)

        self.invoice.balance = Decimal(SMALL_INVOICE_THRESHOLD + 1)
        self.assertTrue(self.billing_record.should_send_email)

    def test_should_send_email_autogenerate_credits(self):
        self.subscription.auto_generate_credits = True
        self.assertFalse(self.billing_record.should_send_email)

        self.invoice.balance = Decimal(SMALL_INVOICE_THRESHOLD + 1)
        self.assertTrue(self.billing_record.should_send_email)

    def test_should_send_email_hidden(self):
        self.assertTrue(self.billing_record.should_send_email)

        self.invoice.is_hidden = True
        self.assertFalse(self.billing_record.should_send_email)
