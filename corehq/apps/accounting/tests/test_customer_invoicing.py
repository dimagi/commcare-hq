import random
from datetime import date
from decimal import Decimal

from django.test import TestCase

from dateutil import relativedelta
from mock import Mock

from dimagi.utils.dates import add_months_to_date

from corehq.apps.accounting import tasks, utils
from corehq.apps.accounting.invoicing import LineItemFactory
from corehq.apps.accounting.models import (
    CreditLine,
    CustomerInvoice,
    DefaultProductPlan,
    DomainUserHistory,
    FeatureType,
    InvoicingPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.accounting.tasks import calculate_users_in_all_domains
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.domain.models import Domain
from corehq.apps.sms.models import INCOMING
from corehq.apps.smsbillables.models import (
    SmsBillable,
    SmsGatewayFee,
    SmsGatewayFeeCriteria,
    SmsUsageFee,
    SmsUsageFeeCriteria,
)
from corehq.apps.smsbillables.tests.generator import (
    arbitrary_sms_billables_for_domain,
)
from corehq.util.dates import get_previous_month_date_range


class BaseCustomerInvoiceCase(BaseAccountingTest):

    is_using_test_plans = False

    @classmethod
    def setUpClass(cls):
        super(BaseCustomerInvoiceCase, cls).setUpClass()

        if cls.is_using_test_plans:
            generator.bootstrap_test_software_plan_versions()

        cls.billing_contact = generator.create_arbitrary_web_user_name()
        cls.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        cls.account = generator.billing_account(
            cls.dimagi_user, cls.billing_contact)
        cls.domain = generator.arbitrary_domain()
        cls.account.is_customer_billing_account = True
        cls.account.save()

        cls.advanced_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        cls.advanced_plan.plan.is_customer_software_plan = True

        cls.subscription_length = 15  # months
        subscription_start_date = date(2016, 2, 23)
        subscription_end_date = add_months_to_date(subscription_start_date, cls.subscription_length)
        cls.subscription = generator.generate_domain_subscription(
            cls.account,
            cls.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
        )

        advanced_subscription_end_date = add_months_to_date(subscription_end_date, 2)
        cls.domain2 = generator.arbitrary_domain()
        cls.sub2 = generator.generate_domain_subscription(
            cls.account,
            cls.domain2,
            date_start=subscription_start_date,
            date_end=advanced_subscription_end_date,
            plan_version=cls.advanced_plan
        )

        cls.domain3 = generator.arbitrary_domain()
        cls.sub3 = generator.generate_domain_subscription(
            cls.account,
            cls.domain3,
            date_start=subscription_start_date,
            date_end=advanced_subscription_end_date,
            plan_version=cls.advanced_plan
        )

        # This subscription should not be included in any customer invoices in these tests
        cls.domain_community = generator.arbitrary_domain()
        cls.sub3 = generator.generate_domain_subscription(
            cls.account,
            cls.domain3,
            date_start=subscription_start_date,
            date_end=advanced_subscription_end_date,
            plan_version=DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.COMMUNITY)
        )

    def tearDown(self):
        for user in self.domain.all_users():
            user.delete(self.domain.name, deleted_by=None)

        for user in self.domain2.all_users():
            user.delete(self.domain2.name, deleted_by=None)

        for user in self.domain3.all_users():
            user.delete(self.domain3.name, deleted_by=None)

        for user in self.domain_community.all_users():
            user.delete(self.domain_community.name, deleted_by=None)

        if self.is_using_test_plans:
            utils.clear_plan_version_cache()

        super(BaseAccountingTest, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.domain2.delete()
        cls.domain3.delete()
        cls.domain_community.delete()

        super(BaseCustomerInvoiceCase, cls).tearDownClass()


class TestCustomerInvoice(BaseCustomerInvoiceCase):

    def test_multiple_subscription_invoice(self):
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(3, self.subscription_length))
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertGreater(invoice.balance, Decimal('0.0000'))
        self.assertEqual(invoice.account, self.account)

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
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('851.6200'))
        self.assertEqual(invoice.account, self.account)

        num_product_line_items = invoice.lineitem_set.get_products().count()
        self.assertEqual(num_product_line_items, 1)

        num_feature_line_items = invoice.lineitem_set.get_features().count()
        self.assertEqual(num_feature_line_items, self.sub2.plan_version.feature_rates.count())

    def test_no_invoice_before_start(self):
        """
        Test that an invoice is not created if its subscriptions didn't start in the previous month.
        """
        calculate_users_in_all_domains(self.subscription.date_start)
        tasks.generate_invoices_based_on_date(self.subscription.date_start)
        self.assertEqual(CustomerInvoice.objects.count(), 0)

    def test_no_invoice_after_end(self):
        """
        No invoices should be generated for the months after the end date of the subscriptions.
        """
        invoice_date = utils.months_from_date(self.sub2.date_end, 2)
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 0)

    def test_deleted_domain_in_multiple_subscription_invoice(self):
        invoice_date = utils.months_from_date(self.subscription.date_start, 2)

        domain_to_be_deleted = generator.arbitrary_domain()
        generator.generate_domain_subscription(
            self.account,
            domain_to_be_deleted,
            date_start=self.sub2.date_start,
            date_end=self.sub2.date_end,
            plan_version=self.advanced_plan
        )
        domain_to_be_deleted.delete(leave_tombstone=True)

        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()

        num_product_line_items = invoice.lineitem_set.get_products().count()
        self.assertEqual(num_product_line_items, 2)


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
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)

        invoice = CustomerInvoice.objects.first()
        product_line_items = invoice.lineitem_set.get_products()
        self.assertEqual(product_line_items.count(), 2)
        product_descriptions = [line_item.base_description for line_item in product_line_items]
        self.assertItemsEqual(product_descriptions, ['One month of CommCare Advanced Edition Software Plan.',
                                                     'One month of CommCare Standard Edition Software Plan.'])
        product_costs = [line_item.base_cost for line_item in product_line_items]
        self.assertItemsEqual(product_costs, [self.product_rate.monthly_fee,
                                              self.advanced_plan.product_rate.monthly_fee])

    def test_product_line_items_in_quarterly_invoice(self):
        self.account.invoicing_plan = InvoicingPlan.QUARTERLY
        self.account.save()
        invoice_date = utils.months_from_date(self.subscription.date_start, 14)
        for months_before_invoice_date in range(3):
            user_date = date(invoice_date.year, invoice_date.month, 1)
            user_date -= relativedelta.relativedelta(months=months_before_invoice_date)
            calculate_users_in_all_domains(user_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('4500.0000'))
        self.assertEqual(invoice.account, self.account)

        # There should be two product line items, with 3 months billed for each
        num_product_line_items = invoice.lineitem_set.get_products().count()
        self.assertEqual(num_product_line_items, 2)
        for product_line_item in invoice.lineitem_set.get_products().all():
            self.assertEqual(product_line_item.quantity, 3)

    def test_product_line_items_in_yearly_invoice(self):
        self.account.invoicing_plan = InvoicingPlan.YEARLY
        self.account.save()
        invoice_date = utils.months_from_date(self.subscription.date_start, 14)
        for months_before_invoice_date in range(12):
            user_date = date(invoice_date.year, invoice_date.month, 1)
            user_date -= relativedelta.relativedelta(months=months_before_invoice_date)
            calculate_users_in_all_domains(user_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('18000.0000'))
        self.assertEqual(invoice.account, self.account)

        # There should be two product line items, with 3 months billed for each
        num_product_line_items = invoice.lineitem_set.get_products().count()
        self.assertEqual(num_product_line_items, 2)
        for product_line_item in invoice.lineitem_set.get_products().all():
            self.assertEqual(product_line_item.quantity, 12)

    def test_subscriptions_marked_do_not_invoice_not_included(self):
        self.subscription.do_not_invoice = True

        invoice_date = utils.months_from_date(self.sub2.date_end, 1)
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('851.6200'))
        self.assertEqual(invoice.account, self.account)

        product_line_items = invoice.lineitem_set.get_products()
        self.assertEqual(product_line_items.count(), 1)
        self.assertEqual(
            product_line_items.first().base_description,
            None
        )
        self.assertEqual(
            product_line_items.first().unit_description,
            '22 days of CommCare Advanced Edition Software Plan. (Jul 1 - Jul 22)'
        )

        num_feature_line_items = invoice.lineitem_set.get_features().count()
        self.assertEqual(num_feature_line_items, self.sub2.plan_version.feature_rates.count())

    def test_account_level_product_credits(self):
        CreditLine.add_credit(
            amount=self.subscription.plan_version.product_rate.monthly_fee / 2,
            account=self.account,
            is_product=True
        )
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('1350.0000'))

    def test_subscription_level_product_credits(self):
        CreditLine.add_credit(
            self.subscription.plan_version.product_rate.monthly_fee / 2,
            is_product=True,
            subscription=self.subscription
        )
        CreditLine.add_credit(
            self.sub2.plan_version.product_rate.monthly_fee / 4,
            is_product=True,
            subscription=self.sub2,
        )
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('1050.0000'))


class TestUserLineItem(BaseCustomerInvoiceCase):

    is_using_test_plans = True

    def setUp(self):
        super(TestUserLineItem, self).setUp()
        self.user_rate = self.subscription.plan_version.feature_rates \
            .filter(feature__feature_type=FeatureType.USER).get()
        self.advanced_rate = self.advanced_plan.feature_rates.filter(feature__feature_type=FeatureType.USER).get()
        self.invoice_date = utils.months_from_date(self.subscription.date_start,
                                                   random.randint(2, self.subscription_length))

    def test_under_limit(self):
        num_users = random.randint(0, self.user_rate.monthly_limit)
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_users)

        num_users_advanced = random.randint(0, self.advanced_rate.monthly_limit)
        generator.arbitrary_commcare_users_for_domain(self.domain2.name, num_users_advanced)

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)

        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('1500.0000'))
        user_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.USER)
        self.assertEqual(user_line_items.count(), 2)
        for user_line_item in user_line_items:
            self.assertEqual(user_line_item.quantity, 0)
            self.assertEqual(user_line_item.subtotal, Decimal('0.0000'))
            self.assertEqual(user_line_item.total, Decimal('0.0000'))
            self.assertIsNone(user_line_item.base_description)
            self.assertEqual(user_line_item.base_cost, Decimal('0.0000'))
            self.assertIsNone(user_line_item.unit_description)
            self.assertEqual(user_line_item.unit_cost, Decimal('1.0000'))

    def test_over_limit(self):
        num_users = self.user_rate.monthly_limit + 1
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_users)

        num_users_advanced = self.advanced_rate.monthly_limit + 1
        generator.arbitrary_commcare_users_for_domain(self.domain2.name, num_users_advanced)

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)

        invoice = CustomerInvoice.objects.first()
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

    def test_account_level_user_credits(self):
        # Add User usage
        num_users = self.user_rate.monthly_limit + 10
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_users)
        num_users_advanced = self.advanced_rate.monthly_limit + 1
        generator.arbitrary_commcare_users_for_domain(self.domain2.name, num_users_advanced)

        # Cover the cost of 1 User
        CreditLine.add_credit(
            amount=Decimal(2.0000),
            feature_type=FeatureType.USER,
            account=self.account,
        )

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal(1509.0000))

    def test_subscription_level_user_credits(self):
        # Add User usage
        num_users = self.user_rate.monthly_limit + 10
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_users)
        num_users_advanced = self.advanced_rate.monthly_limit + 1
        generator.arbitrary_commcare_users_for_domain(self.domain2.name, num_users_advanced)

        # Cover the cost of 1 User on the Standard subscription
        CreditLine.add_credit(
            amount=Decimal(2.0000),
            feature_type=FeatureType.USER,
            subscription=self.subscription
        )
        # Cover the cost of 5 Users on the Advanced subscription
        CreditLine.add_credit(
            amount=Decimal(10.0000),
            feature_type=FeatureType.USER,
            subscription=self.sub2
        )

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal(1500.0000))

    def test_one_subscription_level_user_credit(self):
        # Add User usage
        num_users = self.user_rate.monthly_limit + 10
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_users)
        num_users_advanced = self.advanced_rate.monthly_limit + 1
        generator.arbitrary_commcare_users_for_domain(self.domain2.name, num_users_advanced)

        # Cover the cost of 2 Users on the Advanced subscription
        CreditLine.add_credit(
            amount=Decimal(4.0000),
            feature_type=FeatureType.USER,
            subscription=self.sub2
        )

        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal(1507.0000))


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
        num_sms = self.sms_rate.monthly_limit // 2
        arbitrary_sms_billables_for_domain(
            self.domain, self.sms_date, num_sms, direction=INCOMING
        )
        num_sms_advanced = self.advanced_rate.monthly_limit // 2
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

    def test_subscription_level_sms_credits(self):
        # Add SMS usage
        arbitrary_sms_billables_for_domain(
            self.domain, self.sms_date, self.sms_rate.monthly_limit + 1
        )
        arbitrary_sms_billables_for_domain(
            self.domain2, self.sms_date, num_sms=self.advanced_rate.monthly_limit + 10
        )

        # Cover the cost of 1 SMS on the Standard subscription
        CreditLine.add_credit(
            amount=Decimal(0.7500),
            feature_type=FeatureType.SMS,
            subscription=self.subscription
        )
        # Cover the cost of 10 SMS on the Advanced subscription
        CreditLine.add_credit(
            amount=Decimal(7.5000),
            feature_type=FeatureType.SMS,
            subscription=self.sub2,
        )

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('1500.0000'))

    def test_one_subscription_level_sms_credit(self):
        # Add SMS usage
        arbitrary_sms_billables_for_domain(
            self.domain, self.sms_date, self.sms_rate.monthly_limit + 1
        )
        arbitrary_sms_billables_for_domain(
            self.domain2, self.sms_date, num_sms=self.advanced_rate.monthly_limit + 10
        )

        # Cover the cost of 1 SMS on the Standard subscription
        CreditLine.add_credit(
            amount=Decimal(0.7500),
            feature_type=FeatureType.SMS,
            subscription=self.subscription
        )

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('1507.5000'))

    def test_account_level_sms_credits(self):
        # Add SMS usage
        arbitrary_sms_billables_for_domain(
            self.domain, self.sms_date, self.sms_rate.monthly_limit + 1
        )
        arbitrary_sms_billables_for_domain(
            self.domain2, self.sms_date, num_sms=self.advanced_rate.monthly_limit + 10
        )

        # Cover the cost of 1 SMS
        CreditLine.add_credit(
            amount=Decimal(0.5000),
            feature_type=FeatureType.SMS,
            account=self.account,
        )

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('1507.7500'))

    def _create_sms_line_items(self):
        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        return invoice.lineitem_set.get_feature_by_type(FeatureType.SMS)

    @classmethod
    def _delete_sms_billables(cls):
        SmsBillable.objects.all().delete()
        SmsGatewayFee.objects.all().delete()
        SmsGatewayFeeCriteria.objects.all().delete()
        SmsUsageFee.objects.all().delete()
        SmsUsageFeeCriteria.objects.all().delete()


class TestQuarterlyInvoicing(BaseCustomerInvoiceCase):

    is_using_test_plans = True

    def setUp(self):
        super(TestQuarterlyInvoicing, self).setUp()
        self.user_rate = self.subscription.plan_version.feature_rates \
            .filter(feature__feature_type=FeatureType.USER).get()
        self.advanced_rate = self.advanced_plan.feature_rates.filter(feature__feature_type=FeatureType.USER).get()
        self.initialize_domain_user_history_objects()
        self.sms_rate = self.subscription.plan_version.feature_rates.filter(
            feature__feature_type=FeatureType.SMS
        ).get()
        self.advanced_sms_rate = self.advanced_plan.feature_rates.filter(
            feature__feature_type=FeatureType.SMS
        ).get()
        self.invoice_date = utils.months_from_date(
            self.subscription.date_start, random.randint(2, self.subscription_length)
        )
        self.sms_date = utils.months_from_date(self.invoice_date, -1)

    def initialize_domain_user_history_objects(self):
        record_dates = []
        month_end = self.subscription.date_end
        while month_end > self.subscription.date_start:
            record_dates.append(month_end)
            _, month_end = get_previous_month_date_range(month_end)

        num_users = self.user_rate.monthly_limit + 1
        for record_date in record_dates:
            DomainUserHistory.objects.create(
                domain=self.domain,
                num_users=num_users,
                record_date=record_date
            )

        num_users = self.advanced_rate.monthly_limit + 2
        for record_date in record_dates:
            DomainUserHistory.objects.create(
                domain=self.domain2,
                num_users=num_users,
                record_date=record_date
            )

        for record_date in record_dates:
            DomainUserHistory.objects.create(
                domain=self.domain3,
                num_users=0,
                record_date=record_date
            )

    def test_user_over_limit_in_quarterly_invoice(self):
        num_users = self.user_rate.monthly_limit + 1
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_users)

        num_users_advanced = self.advanced_rate.monthly_limit + 2
        generator.arbitrary_commcare_users_for_domain(self.domain2.name, num_users_advanced)

        self.account.invoicing_plan = InvoicingPlan.QUARTERLY
        self.account.save()
        invoice_date = utils.months_from_date(self.subscription.date_start, 14)
        tasks.generate_invoices_based_on_date(invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)

        invoice = CustomerInvoice.objects.first()
        user_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.USER)
        self.assertEqual(user_line_items.count(), 2)
        for user_line_item in user_line_items:
            if self.user_rate.feature.name == user_line_item.feature_rate.feature.name:
                self.assertEqual(user_line_item.quantity, 3)
            elif user_line_item.feature_rate.feature.name == self.advanced_rate.feature.name:
                self.assertEqual(user_line_item.quantity, 6)

    def test_user_over_limit_in_yearly_invoice(self):
        num_users = self.user_rate.monthly_limit + 1
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_users)

        num_users_advanced = self.advanced_rate.monthly_limit + 2
        generator.arbitrary_commcare_users_for_domain(self.domain2.name, num_users_advanced)

        self.account.invoicing_plan = InvoicingPlan.YEARLY
        self.account.save()
        invoice_date = utils.months_from_date(self.subscription.date_start, 14)
        tasks.generate_invoices_based_on_date(invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)

        invoice = CustomerInvoice.objects.first()
        user_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.USER)
        self.assertEqual(user_line_items.count(), 2)
        for user_line_item in user_line_items:
            if self.user_rate.feature.name == user_line_item.feature_rate.feature.name:
                self.assertEqual(user_line_item.quantity, 12)
            elif user_line_item.feature_rate.feature.name == self.advanced_rate.feature.name:
                self.assertEqual(user_line_item.quantity, 24)

    def test_sms_over_limit_in_quarterly_invoice(self):
        num_sms = random.randint(self.sms_rate.monthly_limit + 1, self.sms_rate.monthly_limit + 2)
        billables = arbitrary_sms_billables_for_domain(
            self.domain, self.sms_date, num_sms
        )
        num_sms_advanced = random.randint(self.advanced_sms_rate.monthly_limit + 1,
                                          self.advanced_sms_rate.monthly_limit + 2)
        advanced_billables = arbitrary_sms_billables_for_domain(
            self.domain2, self.sms_date, num_sms_advanced
        )

        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()

        sms_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.SMS)
        self.assertEqual(sms_line_items.count(), 2)
        for sms_line_item in sms_line_items:
            self.assertIsNone(sms_line_item.base_description)
            self.assertEqual(sms_line_item.base_cost, Decimal('0.0000'))
            self.assertEqual(sms_line_item.quantity, 1)

            if self.advanced_sms_rate.feature == sms_line_item.feature_rate.feature:
                sms_cost = sum(
                    billable.gateway_charge + billable.usage_charge
                    for billable in advanced_billables[self.advanced_sms_rate.monthly_limit:]
                )
            else:
                sms_cost = sum(
                    billable.gateway_charge + billable.usage_charge
                    for billable in billables[self.sms_rate.monthly_limit:]
                )
            self.assertEqual(sms_line_item.unit_cost, sms_cost)
            self.assertEqual(sms_line_item.total, sms_cost)

    def test_sms_over_limit_in_yearly_invoice(self):
        num_sms = random.randint(self.sms_rate.monthly_limit + 1, self.sms_rate.monthly_limit + 2)
        billables = arbitrary_sms_billables_for_domain(
            self.domain, self.sms_date, num_sms
        )
        num_sms_advanced = random.randint(self.advanced_sms_rate.monthly_limit + 1,
                                          self.advanced_sms_rate.monthly_limit + 2)
        advanced_billables = arbitrary_sms_billables_for_domain(
            self.domain2, self.sms_date, num_sms_advanced
        )

        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()

        sms_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.SMS)
        self.assertEqual(sms_line_items.count(), 2)
        for sms_line_item in sms_line_items:
            self.assertIsNone(sms_line_item.base_description)
            self.assertEqual(sms_line_item.base_cost, Decimal('0.0000'))
            self.assertEqual(sms_line_item.quantity, 1)

            if self.advanced_sms_rate.feature == sms_line_item.feature_rate.feature:
                sms_cost = sum(
                    billable.gateway_charge + billable.usage_charge
                    for billable in advanced_billables[self.advanced_sms_rate.monthly_limit:]
                )
            else:
                sms_cost = sum(
                    billable.gateway_charge + billable.usage_charge
                    for billable in billables[self.sms_rate.monthly_limit:]
                )
            self.assertEqual(sms_line_item.unit_cost, sms_cost)
            self.assertEqual(sms_line_item.total, sms_cost)

    def _create_sms_line_items_for_quarter(self):
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        return invoice.lineitem_set.get_feature_by_type(FeatureType.SMS)


class TestDomainsInLineItemForCustomerInvoicing(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestDomainsInLineItemForCustomerInvoicing, cls).setUpClass()

        cls.customer_account = generator.billing_account('test@test.com', 'test@test.com')
        cls.customer_account.is_customer_billing_account = True
        cls.customer_account.save()

        cls.customer_plan_version = DefaultProductPlan.get_default_plan_version()
        cls.customer_plan_version.plan.is_customer_software_plan = True
        cls.customer_plan_version.plan.save()

        cls.mock_customer_invoice = Mock()
        cls.mock_customer_invoice.date_start = date(2019, 5, 1)
        cls.mock_customer_invoice.date_end = date(2019, 5, 31)

        cls.domain = Domain(name='test_domain')
        cls.domain.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()

        super(TestDomainsInLineItemForCustomerInvoicing, cls).tearDownClass()

    def test_past_subscription_is_excluded(self):
        past_subscription = Subscription.new_domain_subscription(
            account=self.customer_account,
            domain=self.domain.name,
            plan_version=self.customer_plan_version,
            date_start=date(2019, 4, 1),
            date_end=date(2019, 5, 1),
        )
        line_item_factory = LineItemFactory(past_subscription, None, self.mock_customer_invoice)
        self.assertEqual(line_item_factory.subscribed_domains, [])

    def test_future_subscription_is_excluded(self):
        future_subscription = Subscription.new_domain_subscription(
            account=self.customer_account,
            domain=self.domain.name,
            plan_version=self.customer_plan_version,
            date_start=date(2019, 6, 1),
            date_end=date(2019, 7, 1),
        )
        line_item_factory = LineItemFactory(future_subscription, None, self.mock_customer_invoice)
        self.assertEqual(line_item_factory.subscribed_domains, [])

    def test_preexisting_subscription_is_included(self):
        preexisting_subscription = Subscription.new_domain_subscription(
            account=self.customer_account,
            domain=self.domain.name,
            plan_version=self.customer_plan_version,
            date_start=date(2019, 4, 30),
            date_end=date(2019, 5, 2),
        )
        line_item_factory = LineItemFactory(preexisting_subscription, None, self.mock_customer_invoice)
        self.assertEqual(line_item_factory.subscribed_domains, [self.domain.name])

    def test_preexisting_subscription_without_end_date_is_included(self):
        preexisting_subscription = Subscription.new_domain_subscription(
            account=self.customer_account,
            domain=self.domain.name,
            plan_version=self.customer_plan_version,
            date_start=date(2019, 4, 30),
        )
        line_item_factory = LineItemFactory(preexisting_subscription, None, self.mock_customer_invoice)
        self.assertEqual(line_item_factory.subscribed_domains, [self.domain.name])

    def test_new_subscription_is_included(self):
        new_subscription = Subscription.new_domain_subscription(
            account=self.customer_account,
            domain=self.domain.name,
            plan_version=self.customer_plan_version,
            date_start=date(2019, 5, 31),
            date_end=date(2019, 6, 1),
        )
        line_item_factory = LineItemFactory(new_subscription, None, self.mock_customer_invoice)
        self.assertEqual(line_item_factory.subscribed_domains, [self.domain.name])

    def test_new_subscription_without_end_date_is_included(self):
        new_subscription = Subscription.new_domain_subscription(
            account=self.customer_account,
            domain=self.domain.name,
            plan_version=self.customer_plan_version,
            date_start=date(2019, 5, 31),
        )
        line_item_factory = LineItemFactory(new_subscription, None, self.mock_customer_invoice)
        self.assertEqual(line_item_factory.subscribed_domains, [self.domain.name])
