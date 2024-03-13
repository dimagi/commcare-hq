import datetime
from decimal import Decimal

from django.core import mail
from django.db import models

from unittest import mock

from dimagi.utils.dates import add_months_to_date

from corehq.apps.accounting import tasks
from corehq.apps.accounting.models import (
    SMALL_INVOICE_THRESHOLD,
    BillingAccount,
    BillingRecord,
    Currency,
    CustomerBillingRecord,
    CustomerInvoice,
    Invoice,
    StripePaymentMethod,
    Subscription,
    SubscriptionType,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests.generator import (
    FakeStripeCardManager,
    FakeStripeCustomerManager,
)
from corehq.apps.domain.models import Domain
from corehq.apps.smsbillables.models import (
    SmsBillable,
    SmsGatewayFee,
    SmsGatewayFeeCriteria,
    SmsUsageFee,
    SmsUsageFeeCriteria,
)
from corehq.util.dates import get_previous_month_date_range
from corehq.apps.accounting.tests.utils import mocked_stripe_api


class TestBillingAccount(BaseAccountingTest):

    def setUp(self):
        super(TestBillingAccount, self).setUp()
        self.billing_contact = generator.create_arbitrary_web_user_name()
        self.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        self.currency = generator.init_default_currency()
        self.billing_account = generator.billing_account(self.dimagi_user, self.billing_contact)

    def test_creation(self):
        self.assertIsNotNone(self.billing_account)

    def test_deletions(self):
        self.assertRaises(models.ProtectedError, self.currency.delete)

    def test_autopay_user(self):
        self.assertFalse(self.billing_account.auto_pay_enabled)

        mail.outbox = []
        autopay_user = generator.create_arbitrary_web_user_name()
        self.billing_account.update_autopay_user(autopay_user, None)
        self.assertEqual(len(mail.outbox), 1)
        self.assertTrue(self.billing_account.auto_pay_enabled)
        self.assertEqual(self.billing_account.auto_pay_user, autopay_user)

        mail.outbox = []
        other_autopay_user = generator.create_arbitrary_web_user_name()
        self.billing_account.update_autopay_user(other_autopay_user, None)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(self.billing_account.auto_pay_user, other_autopay_user)

    def tearDown(self):
        SmsBillable.objects.all().delete()
        SmsGatewayFee.objects.all().delete()
        SmsGatewayFeeCriteria.objects.all().delete()
        SmsUsageFee.objects.all().delete()
        SmsUsageFeeCriteria.objects.all().delete()
        BillingAccount.objects.all().delete()
        Currency.objects.all().delete()
        super(TestBillingAccount, self).tearDown()


class TestSubscription(BaseAccountingTest):

    def setUp(self):
        super(TestSubscription, self).setUp()
        self.billing_contact = generator.create_arbitrary_web_user_name()
        self.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        self.domain = Domain(name='test')
        self.domain.save()
        self.currency = generator.init_default_currency()
        self.account = generator.billing_account(self.dimagi_user, self.billing_contact)

        self.subscription_length = 15  # months
        subscription_start_date = datetime.date(2016, 2, 23)
        subscription_end_date = add_months_to_date(subscription_start_date, self.subscription_length)
        self.subscription = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
        )

    def test_creation(self):
        self.assertIsNotNone(self.subscription)

    def test_no_activation(self):
        tasks.activate_subscriptions(based_on_date=self.subscription.date_start - datetime.timedelta(30))
        subscription = Subscription.visible_objects.get(id=self.subscription.id)
        self.assertFalse(subscription.is_active)

    def test_no_activation_date_start_equals_date_end(self):
        self.subscription.date_end = self.subscription.date_start
        self.subscription.save()
        tasks.activate_subscriptions(based_on_date=self.subscription.date_start)
        subscription = Subscription.visible_objects.get(id=self.subscription.id)
        self.assertFalse(subscription.is_active)

    def test_no_activation_after_date_end(self):
        with mock.patch('corehq.apps.accounting.tasks.date') as mock_date:
            mock_date.today.return_value = self.subscription.date_end
            tasks.activate_subscriptions()
        subscription = Subscription.visible_objects.get(id=self.subscription.id)
        self.assertFalse(subscription.is_active)

    def test_activation(self):
        tasks.activate_subscriptions(based_on_date=self.subscription.date_start)
        subscription = Subscription.visible_objects.get(id=self.subscription.id)
        self.assertTrue(subscription.is_active)

    def test_no_deactivation(self):
        tasks.activate_subscriptions(based_on_date=self.subscription.date_start)
        tasks.deactivate_subscriptions(based_on_date=self.subscription.date_end - datetime.timedelta(30))
        subscription = Subscription.visible_objects.get(id=self.subscription.id)
        self.assertTrue(subscription.is_active)

    def test_deactivation(self):
        tasks.deactivate_subscriptions(based_on_date=self.subscription.date_end)
        subscription = Subscription.visible_objects.get(id=self.subscription.id)
        self.assertFalse(subscription.is_active)

    def test_deletions(self):
        self.assertRaises(models.ProtectedError, self.account.delete)
        self.assertRaises(models.ProtectedError, self.subscription.plan_version.delete)
        self.assertRaises(models.ProtectedError, self.subscription.subscriber.delete)

    def test_is_hidden_to_ops(self):
        self.subscription.is_hidden_to_ops = True
        self.subscription.save()
        self.assertEqual(0, len(Subscription.visible_objects.filter(id=self.subscription.id)))

        self.subscription.is_hidden_to_ops = False
        self.subscription.save()
        self.assertEqual(1, len(Subscription.visible_objects.filter(id=self.subscription.id)))

    def test_next_subscription(self):
        this_subscription_date_end = self.subscription.date_end
        already_canceled_future_subscription = generator.generate_domain_subscription(  # noqa
            self.account,
            self.domain,
            date_start=this_subscription_date_end,
            date_end=this_subscription_date_end
        )
        next_future_subscription = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=this_subscription_date_end,
            date_end=add_months_to_date(this_subscription_date_end, 1),
        )
        self.assertEqual(self.subscription.next_subscription, next_future_subscription)

    def test_get_active_domains_for_account(self):
        tasks.activate_subscriptions(based_on_date=self.subscription.date_start)
        test_domains = ['test']
        domains = Subscription.get_active_domains_for_account(self.account)
        self.assertEqual(list(domains), test_domains)

    def tearDown(self):
        self.domain.delete()

        super(TestSubscription, self).tearDown()


class TestBillingRecord(BaseAccountingTest):

    def setUp(self):
        super(TestBillingRecord, self).setUp()
        self.billing_contact = generator.create_arbitrary_web_user_name()
        self.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        self.domain = Domain(name='test')
        self.domain.save()
        self.invoice_start, self.invoice_end = get_previous_month_date_range()
        self.currency = generator.init_default_currency()
        self.account = generator.billing_account(self.dimagi_user, self.billing_contact)

        self.subscription_length = 4  # months
        subscription_start_date = datetime.date(2016, 2, 23)
        subscription_end_date = add_months_to_date(subscription_start_date, self.subscription_length)
        self.subscription = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
        )
        self.invoice = Invoice(
            subscription=self.subscription,
            date_start=self.invoice_start,
            date_end=self.invoice_end,
            is_hidden=False,
        )
        self.billing_record = BillingRecord(invoice=self.invoice)

    def tearDown(self):
        self.domain.delete()
        super(TestBillingRecord, self).tearDown()

    def test_should_send_email(self):
        self.assertTrue(self.billing_record.should_send_email)

    def test_should_send_email_contracted(self):
        self.subscription.service_type = SubscriptionType.IMPLEMENTATION
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


class TestCustomerBillingRecord(BaseAccountingTest):

    def setUp(self):
        super(TestCustomerBillingRecord, self).setUp()
        self.billing_contact = generator.create_arbitrary_web_user_name()
        self.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        self.domain = Domain(name='test')
        self.domain.save()
        self.invoice_start, self.invoice_end = get_previous_month_date_range()
        self.currency = generator.init_default_currency()
        self.account = generator.billing_account(self.dimagi_user, self.billing_contact)
        self.account.is_customer_billing_account = True
        self.account.save()

        self.subscription_length = 4  # months
        subscription_start_date = datetime.date(2016, 2, 23)
        subscription_end_date = add_months_to_date(subscription_start_date, self.subscription_length)
        self.subscription = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
        )
        self.invoice = CustomerInvoice(
            account=self.account,
            date_start=self.invoice_start,
            date_end=self.invoice_end,
            is_hidden=False
        )
        self.customer_billing_record = CustomerBillingRecord(invoice=self.invoice)

    def tearDown(self):
        self.domain.delete()
        super(TestCustomerBillingRecord, self).tearDown()

    def test_should_send_email(self):
        self.assertTrue(self.customer_billing_record.should_send_email)

    def test_should_send_email_hidden(self):
        self.assertTrue(self.customer_billing_record.should_send_email)

        self.invoice.is_hidden = True
        self.assertFalse(self.customer_billing_record.should_send_email)


@mock.patch.object(StripePaymentMethod, 'customer')
class TestStripePaymentMethod(BaseAccountingTest):

    def setUp(self):
        super(TestStripePaymentMethod, self).setUp()

        self.web_user = generator.create_arbitrary_web_user_name()
        self.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)

        self.fake_card = FakeStripeCardManager.create_card()
        self.fake_stripe_customer = FakeStripeCustomerManager.create_customer(cards=[self.fake_card])

        self.currency = generator.init_default_currency()
        self.billing_account = generator.billing_account(self.dimagi_user, self.web_user)
        self.billing_account_2 = generator.billing_account(self.dimagi_user, self.web_user)

        self.payment_method = StripePaymentMethod(web_user=self.web_user,
                                                  customer_id=self.fake_stripe_customer.id)
        self.payment_method.save()

    @mock.patch('corehq.apps.accounting.models.BillingAccount._send_autopay_card_added_email')
    @mocked_stripe_api()
    def test_set_autopay(self, mock_send_email, fake_customer):
        fake_customer.__get__ = mock.Mock(return_value=self.fake_stripe_customer)
        self.assertEqual(self.billing_account.auto_pay_user, None)
        self.assertFalse(self.billing_account.auto_pay_enabled)

        self.payment_method.set_autopay(self.fake_card, self.billing_account, None)
        self.assertEqual(self.fake_card.metadata, {"auto_pay_{}".format(self.billing_account.id): 'True'})
        self.assertEqual(self.billing_account.auto_pay_user, self.web_user)
        self.assertTrue(self.billing_account.auto_pay_enabled)

        self.payment_method.set_autopay(self.fake_card, self.billing_account_2, None)
        self.assertEqual(self.fake_card.metadata, {"auto_pay_{}".format(self.billing_account.id): 'True',
                                                   "auto_pay_{}".format(self.billing_account_2.id): 'True'})

        other_web_user = generator.create_arbitrary_web_user_name()
        other_payment_method = StripePaymentMethod(web_user=other_web_user)
        different_fake_card = FakeStripeCardManager.create_card()

        other_payment_method.set_autopay(different_fake_card, self.billing_account, None)
        self.assertEqual(self.billing_account.auto_pay_user, other_web_user)
        self.assertTrue(different_fake_card.metadata["auto_pay_{}".format(self.billing_account.id)])
        self.assertFalse(self.fake_card.metadata["auto_pay_{}".format(self.billing_account.id)] == 'True')

    @mocked_stripe_api()
    def test_unset_autopay(self, fake_customer):
        fake_customer.__get__ = mock.Mock(return_value=self.fake_stripe_customer)
        self.payment_method.set_autopay(self.fake_card, self.billing_account, None)
        self.assertEqual(self.fake_card.metadata, {"auto_pay_{}".format(self.billing_account.id): 'True'})

        self.payment_method.unset_autopay(self.fake_card, self.billing_account)

        self.assertEqual(self.fake_card.metadata, {"auto_pay_{}".format(self.billing_account.id): 'False'})
        self.assertIsNone(self.billing_account.auto_pay_user)
        self.assertFalse(self.billing_account.auto_pay_enabled)
