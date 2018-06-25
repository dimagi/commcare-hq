from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from decimal import Decimal
import random
import datetime

from dimagi.utils.dates import add_months_to_date
from corehq.util.dates import get_previous_month_date_range

from corehq.apps.accounting import utils
from corehq.apps.accounting.invoicing import CustomerAccountInvoiceFactory
from corehq.apps.accounting.models import (
    DefaultProductPlan,
    FeatureType,
    SoftwarePlanEdition
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import (
    SmsBillable,
    SmsGatewayFee,
    SmsGatewayFeeCriteria,
    SmsUsageFee,
    SmsUsageFeeCriteria,
)
from corehq.apps.smsbillables.tests.generator import arbitrary_sms_billables_for_domain


class BaseCustomerInvoiceCase(BaseAccountingTest):

    @classmethod
    def setUpClass(cls):
        super(BaseCustomerInvoiceCase, cls).setUpClass()

        cls.billing_contact = generator.create_arbitrary_web_user_name()
        cls.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        cls.currency = generator.init_default_currency()
        cls.account = generator.billing_account(
            cls.dimagi_user, cls.billing_contact)
        cls.domain = generator.arbitrary_domain()
        cls.account.is_customer_billing_account = True
        cls.account.save()

        cls.advanced_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        cls.advanced_plan.plan.is_customer_software_plan = True

        cls.subscription_length = 15  # months
        subscription_start_date = datetime.date(2016, 2, 23)
        subscription_end_date = add_months_to_date(subscription_start_date, cls.subscription_length)
        cls.subscription = generator.generate_domain_subscription(
            cls.account,
            cls.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
        )
        cls.subscription.plan_version.plan.is_customer_software_plan = True

        advanced_subscription_end_date = add_months_to_date(subscription_end_date, 2)
        cls.domain2 = generator.arbitrary_domain()
        cls.sub2 = generator.generate_domain_subscription(
            cls.account,
            cls.domain2,
            date_start=subscription_start_date,
            date_end=advanced_subscription_end_date,
            plan_version=cls.advanced_plan
        )
        cls.sub2.plan_version.plan.is_customer_software_plan = True

        cls.domain3 = generator.arbitrary_domain()
        cls.sub3 = generator.generate_domain_subscription(
            cls.account,
            cls.domain3,
            date_start=subscription_start_date,
            date_end=advanced_subscription_end_date,
            plan_version=cls.advanced_plan
        )
        cls.sub3.plan_version.plan.is_customer_software_plan = True

    def tearDown(self):
        for user in self.domain.all_users():
            user.delete()

        for user in self.domain2.all_users():
            user.delete()

        for user in self.domain3.all_users():
            user.delete()

        super(BaseAccountingTest, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.domain2.delete()
        cls.domain3.delete()

        super(BaseCustomerInvoiceCase, cls).tearDownClass()


class TestCustomerInvoice(BaseCustomerInvoiceCase):

    def test_multiple_subscription_invoice(self):
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))
        invoice_start, invoice_end = get_previous_month_date_range(invoice_date)
        invoice_factory = CustomerAccountInvoiceFactory(
            account=self.account,
            date_start=invoice_start,
            date_end=invoice_end
        )
        invoice_factory.create_invoice()

        # The customer invoice will be added to one of the subscriptions invoice_set
        invoice_set = self.subscription.invoice_set.union(self.sub2.invoice_set.all(),
                                                          self.sub3.invoice_set.all())
        self.assertEqual(invoice_set.count(), 1)

        invoice = invoice_set.first()
        self.assertGreater(invoice.balance, Decimal('0.0000'))
        self.assertEqual(invoice.account, self.account)
        self.assertIn(invoice.subscription, [self.subscription, self.sub2, self.sub3])
        self.assertIn(invoice.subscription.subscriber.domain,
                      [self.domain.name, self.domain2.name, self.domain3.name])

        num_product_line_items = invoice.lineitem_set.get_products().count()
        self.assertEqual(num_product_line_items, 2)

        num_feature_line_items = invoice.lineitem_set.get_features().count()
        self.assertEqual(num_feature_line_items, self.subscription.plan_version.feature_rates.count() +
                         self.sub2.plan_version.feature_rates.count())

    def test_only_invoice_active_subscriptions(self):
        """
        Test that only active subscriptions are invoiced.
        Two subscriptions of the same plan only create one product line item and one set of feature line items
        """
        invoice_date = utils.months_from_date(self.sub2.date_end, 1)
        invoice_start, invoice_end = get_previous_month_date_range(invoice_date)
        invoice_factory = CustomerAccountInvoiceFactory(
            account=self.account,
            date_start=invoice_start,
            date_end=invoice_end
        )
        invoice_factory.create_invoice()
        invoice_set = self.subscription.invoice_set.union(self.sub2.invoice_set.all(), self.sub3.invoice_set.all())
        self.assertEqual(invoice_set.count(), 1)

        invoice = invoice_set.first()
        self.assertEqual(invoice.balance, Decimal('1000.0000'))
        self.assertEqual(invoice.account, self.account)
        self.assertIn(invoice.subscription, [self.sub2, self.sub3])
        self.assertIn(invoice.subscription.subscriber.domain,[self.domain2.name, self.domain3.name])

        num_product_line_items = invoice.lineitem_set.get_products().count()
        self.assertEqual(num_product_line_items, 1)

        num_feature_line_items = invoice.lineitem_set.get_features().count()
        self.assertEqual(num_feature_line_items, self.sub2.plan_version.feature_rates.count())

    def test_no_invoice_before_start(self):
        """
        Test that an invoice is not created if its subscriptions didn't start in the previous month.
        """
        invoice_start, invoice_end = get_previous_month_date_range(self.subscription.date_start)
        invoice_factory = CustomerAccountInvoiceFactory(
            account=self.account,
            date_start=invoice_start,
            date_end=invoice_end
        )
        invoice_factory.create_invoice()
        invoice_set = self.subscription.invoice_set.union(self.sub2.invoice_set.all(), self.sub3.invoice_set.all())
        self.assertEqual(invoice_set.count(), 0)

    def test_no_invoice_after_end(self):
        """
        No invoices should be generated for the months after the end date of the subscriptions.
        """
        invoice_date = utils.months_from_date(self.sub2.date_end, 2)
        invoice_start, invoice_end = get_previous_month_date_range(invoice_date)
        invoice_factory = CustomerAccountInvoiceFactory(
            account=self.account,
            date_start=invoice_start,
            date_end=invoice_end
        )
        invoice_factory.create_invoice()
        invoice_set = self.subscription.invoice_set.union(self.sub2.invoice_set.all(), self.sub3.invoice_set.all())
        self.assertEqual(invoice_set.count(), 0)


class TestProductLineItem(BaseCustomerInvoiceCase):
    """
        Tests that the Product line item is properly generated in an invoice.
        Customer level Invoice do not prorate monthly costs
    """

    def setUp(self):
        super(TestProductLineItem, self).setUp()
        self.product_rate = self.subscription.plan_version.product_rate

    def test_product_line_items(self):
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))
        invoice_start, invoice_end = get_previous_month_date_range(invoice_date)
        invoice_factory = CustomerAccountInvoiceFactory(
            account=self.account,
            date_start=invoice_start,
            date_end=invoice_end
        )
        invoice_factory.create_invoice()
        invoice_set = self.subscription.invoice_set.union(self.sub2.invoice_set.all(), self.sub3.invoice_set.all())
        self.assertEqual(invoice_set.count(), 1)

        invoice = invoice_set.first()
        product_line_items = invoice.lineitem_set.get_products()
        self.assertEqual(product_line_items.count(), 2)
        for line_item in product_line_items:
            self.assertTrue(line_item.base_description == 'One month of CommCare Advanced Software Plan.' or
                            line_item.base_description == 'One month of CommCare Standard Software Plan.')
            self.assertTrue(line_item.base_cost == self.product_rate.monthly_fee or
                            line_item.base_cost == self.advanced_plan.product_rate.monthly_fee)


class TestUserLineItem(BaseCustomerInvoiceCase):
    def setUp(self):
        super(TestUserLineItem, self).setUp()
        self.user_rate = self.subscription.plan_version.feature_rates \
            .filter(feature__feature_type=FeatureType.USER).get()
        self.advanced_rate = self.advanced_plan.feature_rates.filter(feature__feature_type=FeatureType.USER).get()

    def test_under_limit(self):
        num_users = random.randint(0, self.user_rate.monthly_limit)
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_users)

        num_users_advanced = random.randint(0, self.advanced_rate.monthly_limit)
        generator.arbitrary_commcare_users_for_domain(self.domain2.name, num_users_advanced)

        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))
        invoice_start, invoice_end = get_previous_month_date_range(invoice_date)
        invoice_factory = CustomerAccountInvoiceFactory(
            account=self.account,
            date_start=invoice_start,
            date_end=invoice_end
        )
        invoice_factory.create_invoice()
        invoice_set = self.subscription.invoice_set.union(self.sub2.invoice_set.all(), self.sub3.invoice_set.all())
        self.assertEqual(invoice_set.count(), 1)

        invoice = invoice_set.first()
        self.assertEqual(invoice.balance, Decimal('1100.0000'))
        user_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.USER)
        self.assertEqual(user_line_items.count(), 2)
        for user_line_item in user_line_items:
            self.assertEqual(user_line_item.quantity, 0)
            self.assertEqual(user_line_item.subtotal, Decimal('0.0000'))
            self.assertEqual(user_line_item.total, Decimal('0.0000'))
            self.assertIsNone(user_line_item.base_description)
            self.assertEqual(user_line_item.base_cost, Decimal('0.0000'))
            self.assertIsNone(user_line_item.unit_description)
            self.assertEqual(user_line_item.unit_cost, Decimal('2.0000'))

    def test_over_limit(self):
        num_users = self.user_rate.monthly_limit + 1
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_users)

        num_users_advanced = self.advanced_rate.monthly_limit + 1
        generator.arbitrary_commcare_users_for_domain(self.domain2.name, num_users_advanced)

        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))
        invoice_start, invoice_end = get_previous_month_date_range(invoice_date)
        invoice_factory = CustomerAccountInvoiceFactory(
            account=self.account,
            date_start=invoice_start,
            date_end=invoice_end
        )
        invoice_factory.create_invoice()
        invoice_set = self.subscription.invoice_set.union(self.sub2.invoice_set.all(), self.sub3.invoice_set.all())
        self.assertEqual(invoice_set.count(), 1)

        invoice = invoice_set.first()
        user_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.USER)
        self.assertEqual(user_line_items.count(), 2)
        for user_line_item in user_line_items:
            self.assertIsNone(user_line_item.base_description)
            self.assertEqual(user_line_item.base_cost, Decimal('0.0000'))
            num_to_charge = num_users - self.user_rate.monthly_limit
            self.assertEqual(num_to_charge, user_line_item.quantity)
            if self.user_rate.feature.name == user_line_item.feature_rate.feature.name:
                self.assertEqual(user_line_item.unit_cost, self.user_rate.per_excess_fee)
                self.assertEqual(user_line_item.total, self.user_rate.per_excess_fee * num_to_charge)
                self.assertEqual(user_line_item.subtotal, self.user_rate.per_excess_fee * num_to_charge)
            elif user_line_item.feature_rate.feature.name == self.advanced_rate.feature.name:
                self.assertEqual(user_line_item.unit_cost, self.advanced_rate.per_excess_fee)
                self.assertEqual(user_line_item.total, self.advanced_rate.per_excess_fee * num_to_charge)
                self.assertEqual(user_line_item.subtotal, self.advanced_rate.per_excess_fee * num_to_charge)


class TestSmsLineItem(BaseCustomerInvoiceCase):

    def setUp(self):
        super(TestSmsLineItem, self).setUp()
        self.sms_rate = self.subscription.plan_version.feature_rates.filter(
            feature__feature_type=FeatureType.SMS
        ).get()
        self.advanced_rate = self.advanced_plan.feature_rates.filter(feature__feature_type=FeatureType.SMS).get()
        self.invoice_date = utils.months_from_date(
            self.subscription.date_start, random.randint(2, self.subscription_length)
        )
        self.sms_date = utils.months_from_date(self.invoice_date, -1)

    def tearDown(self):
        self._delete_sms_billables()
        super(TestSmsLineItem, self).tearDown()

    def test_under_limit(self):
        num_sms = random.randint(0, self.sms_rate.monthly_limit // 2)
        arbitrary_sms_billables_for_domain(
            self.domain, self.sms_date, num_sms, direction=INCOMING
        )
        num_sms_advanced = random.randint(0, self.advanced_rate.monthly_limit // 2)
        arbitrary_sms_billables_for_domain(
            self.domain2, self.sms_date, num_sms_advanced, direction=INCOMING
        )

        sms_line_items = self._create_sms_line_items()
        self.assertEqual(sms_line_items.count(), 2)
        for sms_line_item in sms_line_items:
            self.assertIsNone(sms_line_item.base_description)
            self.assertEqual(sms_line_item.base_cost, Decimal('0.0000'))
            self.assertEqual(sms_line_item.quantity, 1)
            self.assertEqual(sms_line_item.unit_cost, Decimal('0.0000'))
            self.assertIsNotNone(sms_line_item.unit_description)
            self.assertEqual(sms_line_item.subtotal, Decimal('0.0000'))
            self.assertEqual(sms_line_item.total, Decimal('0.0000'))

    def test_over_limit(self):
        num_sms = random.randint(self.sms_rate.monthly_limit + 1, self.sms_rate.monthly_limit + 2)
        billables = arbitrary_sms_billables_for_domain(
            self.domain, self.sms_date, num_sms
        )
        num_sms_advanced = random.randint(self.advanced_rate.monthly_limit + 1,
                                          self.advanced_rate.monthly_limit + 2)
        advanced_billables = arbitrary_sms_billables_for_domain(
            self.domain2, self.sms_date, num_sms_advanced
        )

        sms_line_items = self._create_sms_line_items()
        self.assertEqual(sms_line_items.count(), 2)
        for sms_line_item in sms_line_items:
            self.assertIsNone(sms_line_item.base_description)
            self.assertEqual(sms_line_item.base_cost, Decimal('0.0000'))
            self.assertEqual(sms_line_item.quantity, 1)

            if self.advanced_rate.feature == sms_line_item.feature_rate.feature:
                sms_cost = sum(
                    billable.gateway_charge + billable.usage_charge
                    for billable in advanced_billables[self.advanced_rate.monthly_limit:]
                )
            else:
                sms_cost = sum(
                    billable.gateway_charge + billable.usage_charge
                    for billable in billables[self.sms_rate.monthly_limit:]
                )
            self.assertEqual(sms_line_item.unit_cost, sms_cost)
            self.assertEqual(sms_line_item.total, sms_cost)

    def _create_sms_line_items(self):
        invoice_start, invoice_end = get_previous_month_date_range(self.invoice_date)
        invoice_factory = CustomerAccountInvoiceFactory(
            account=self.account,
            date_start=invoice_start,
            date_end=invoice_end
        )
        invoice_factory.create_invoice()
        invoice_set = self.subscription.invoice_set.union(self.sub2.invoice_set.all(), self.sub3.invoice_set.all())
        self.assertEqual(invoice_set.count(), 1)
        invoice = invoice_set.first()
        return invoice.lineitem_set.get_feature_by_type(FeatureType.SMS)

    @classmethod
    def _delete_sms_billables(cls):
        SmsBillable.objects.all().delete()
        SmsGatewayFee.objects.all().delete()
        SmsGatewayFeeCriteria.objects.all().delete()
        SmsUsageFee.objects.all().delete()
        SmsUsageFeeCriteria.objects.all().delete()
