import random
from datetime import date
from decimal import Decimal

from django.test import TestCase

from dateutil import relativedelta
from unittest.mock import Mock

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
from corehq.apps.domain.shortcuts import create_domain


class BaseCustomerInvoiceCase(BaseAccountingTest):

    is_using_test_plans = False

    @classmethod
    def setUpClass(cls):
        super(BaseCustomerInvoiceCase, cls).setUpClass()

        # In the test, we want to setup the senario mimic how Ops will setup enterprise account
        # Only one subscription should have do_not_invoice=False, this subscription will be the main subscription
        # All other subscriptions should have do_not_invoice=True and the same plan as the main subscription has

        if cls.is_using_test_plans:
            generator.bootstrap_test_software_plan_versions()
            cls.addClassCleanup(utils.clear_plan_version_cache)

        cls.billing_contact = generator.create_arbitrary_web_user_name()
        cls.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        cls.account = generator.billing_account(
            cls.dimagi_user, cls.billing_contact)
        cls.account.is_customer_billing_account = True
        cls.account.save()

        cls.advanced_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        cls.advanced_plan.plan.is_customer_software_plan = True

        # This will be the domain with the main subscription
        cls.main_domain = cls._create_domain("main domain")
        cls.main_subscription_length = 15  # months
        main_subscription_start_date = date(2016, 2, 23)
        main_subscription_end_date = add_months_to_date(main_subscription_start_date, cls.main_subscription_length)

        cls.main_subscription = generator.generate_domain_subscription(
            cls.account,
            cls.main_domain,
            date_start=main_subscription_start_date,
            date_end=main_subscription_end_date,
            plan_version=cls.advanced_plan,
        )

        cls.non_main_subscription_length = 10  # months
        non_main_subscription_end_date = add_months_to_date(main_subscription_start_date,
                                                            cls.non_main_subscription_length)
        cls.non_main_domain1 = cls._create_domain("non main domain 1")
        cls.non_main_sub1 = generator.generate_domain_subscription(
            cls.account,
            cls.non_main_domain1,
            date_start=main_subscription_start_date,
            date_end=non_main_subscription_end_date,
            plan_version=cls.advanced_plan,
            do_not_invoice=True
        )

        cls.non_main_domain2 = cls._create_domain("non main domain 2")
        cls.non_main_sub2 = generator.generate_domain_subscription(
            cls.account,
            cls.non_main_domain2,
            date_start=main_subscription_start_date,
            date_end=non_main_subscription_end_date,
            plan_version=cls.advanced_plan,
            do_not_invoice=True
        )

    def cleanUpUser(self):
        for user in self.main_domain.all_users():
            user.delete(self.main_domain.name, deleted_by=None)

        for user in self.non_main_domain1.all_users():
            user.delete(self.non_main_domain1.name, deleted_by=None)

        for user in self.non_main_domain2.all_users():
            user.delete(self.non_main_domain2.name, deleted_by=None)

    @classmethod
    def _create_domain(cls, name):
        domain_obj = create_domain(name)
        cls.addClassCleanup(domain_obj.delete)
        return domain_obj

    def add_domain_feature_rate(self, monthly_limit, per_excess_fee,
                                bundled_mobile_workers=0):
        from corehq.apps.accounting.models import BundledFeatureUnit, Feature, FeatureRate
        domain_feature, __ = Feature.objects.get_or_create(
            name="Domain", defaults={"feature_type": FeatureType.DOMAIN})
        rate = FeatureRate.objects.create(
            feature=domain_feature,
            monthly_fee=Decimal('0.00'),
            monthly_limit=monthly_limit,
            per_excess_fee=per_excess_fee,
        )
        if bundled_mobile_workers:
            BundledFeatureUnit.objects.create(
                feature_rate=rate,
                feature_type=FeatureType.USER,
                quantity_per_unit=bundled_mobile_workers,
            )
        self.main_subscription.plan_version.feature_rates.add(rate)
        return rate


class TestCustomerInvoice(BaseCustomerInvoiceCase):

    def test_multiple_subscription_invoice(self):
        invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start,
                                              random.randint(3, self.non_main_subscription_length))
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('1200.0000'))
        self.assertEqual(invoice.account, self.account)

        num_product_line_items = invoice.lineitem_set.get_products().count()
        self.assertEqual(num_product_line_items, 1)

        num_feature_line_items = invoice.lineitem_set.get_features().count()
        self.assertEqual(num_feature_line_items, self.main_subscription.plan_version.feature_rates.count())

    def test_no_invoice_before_start(self):
        """
        Test that an invoice is not created if its subscriptions didn't start in the previous month.
        """
        calculate_users_in_all_domains(self.main_subscription.date_start)
        tasks.generate_invoices_based_on_date(self.main_subscription.date_start)
        self.assertEqual(CustomerInvoice.objects.count(), 0)

    def test_no_invoice_after_end(self):
        """
        No invoices should be generated for the months after the end date of the subscriptions.
        """
        invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_end, 2)
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 0)

    def test_deleted_domain_in_multiple_subscription_invoice(self):
        """
        Test the customer invoice can still be created after one of the domains was deleted
        """
        invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start, 2)

        domain_to_be_deleted = generator.arbitrary_domain()
        generator.generate_domain_subscription(
            self.account,
            domain_to_be_deleted,
            date_start=self.main_subscription.date_start,
            date_end=self.main_subscription.date_end,
            plan_version=self.advanced_plan
        )
        domain_to_be_deleted.delete(leave_tombstone=True)

        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()

        num_product_line_items = invoice.lineitem_set.get_products().count()
        self.assertEqual(num_product_line_items, 1)


class TestProductLineItem(BaseCustomerInvoiceCase):
    """
        Tests that the Product line item is properly generated in an invoice.
        Customer level Invoice do not prorate monthly costs
    """

    def setUp(self):
        super(TestProductLineItem, self).setUp()
        self.product_rate = self.main_subscription.plan_version.product_rate

    def test_product_line_items(self):
        invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start,
                                              random.randint(2, self.main_subscription_length))
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)

        invoice = CustomerInvoice.objects.first()
        product_line_item_count = invoice.lineitem_set.get_products().count()
        self.assertEqual(product_line_item_count, 1)
        product_line_item = invoice.lineitem_set.get_products().first()
        product_description = product_line_item.base_description
        self.assertEqual(product_description,
                         'One month of CommCare Advanced Edition - Pay Monthly Software Plan.')
        product_cost = product_line_item.base_cost
        self.assertEqual(product_cost, self.product_rate.monthly_fee)

    def test_product_line_items_in_quarterly_invoice(self):
        self.account.invoicing_plan = InvoicingPlan.QUARTERLY
        self.account.save()
        invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start, 14)
        for months_before_invoice_date in range(3):
            user_date = date(invoice_date.year, invoice_date.month, 1)
            user_date -= relativedelta.relativedelta(months=months_before_invoice_date)
            calculate_users_in_all_domains(user_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('3600.0000'))
        self.assertEqual(invoice.account, self.account)

        num_product_line_item = invoice.lineitem_set.get_products().count()
        self.assertEqual(num_product_line_item, 1)
        product_line_item = invoice.lineitem_set.get_products().first()
        self.assertEqual(product_line_item.quantity, 3)

    def test_product_line_items_in_yearly_invoice(self):
        self.account.invoicing_plan = InvoicingPlan.YEARLY
        self.account.save()
        invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start, 14)
        for months_before_invoice_date in range(12):
            user_date = date(invoice_date.year, invoice_date.month, 1)
            user_date -= relativedelta.relativedelta(months=months_before_invoice_date)
            calculate_users_in_all_domains(user_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('14400.0000'))
        self.assertEqual(invoice.account, self.account)

        num_product_line_items = invoice.lineitem_set.get_products()
        self.assertEqual(num_product_line_items.count(), 1)
        product_line_item = invoice.lineitem_set.get_products().first()
        self.assertEqual(product_line_item.quantity, 12)

    def test_account_level_product_credits(self):
        CreditLine.add_credit(
            amount=self.main_subscription.plan_version.product_rate.monthly_fee / 2,
            account=self.account,
            is_product=True
        )
        invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start,
                                              random.randint(2, self.main_subscription_length))
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('600.0000'))

    def test_subscription_level_product_credits(self):
        CreditLine.add_credit(
            self.main_subscription.plan_version.product_rate.monthly_fee / 2,
            is_product=True,
            subscription=self.main_subscription
        )
        invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start,
                                              random.randint(2, self.main_subscription_length))
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('600.0000'))


class TestUserLineItem(BaseCustomerInvoiceCase):

    is_using_test_plans = True

    def setUp(self):
        super(TestUserLineItem, self).setUp()
        self.user_rate = self.main_subscription.plan_version.feature_rates \
            .filter(feature__feature_type=FeatureType.USER).get()
        self.invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start,
                                                   random.randint(2, self.non_main_subscription_length))

    def test_unlimited_monthly_limit_charges_nothing(self):
        from corehq.apps.accounting.models import UNLIMITED_FEATURE_USAGE
        self.user_rate.monthly_limit = UNLIMITED_FEATURE_USAGE
        self.user_rate.save()
        # Even with zero users, max(total - (-1), 0) would charge quantity 1
        # per month-end without the sentinel guard.
        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        invoice = CustomerInvoice.objects.first()
        user_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.USER).first()
        self.assertEqual(user_line_item.quantity, 0)
        self.assertEqual(user_line_item.total, Decimal('0.0000'))
        self.assertIsNone(user_line_item.unit_description)

    def test_under_limit(self):
        num_users_main_domain = random.randint(0, self.user_rate.monthly_limit // 2)
        generator.arbitrary_commcare_users_for_domain(self.main_domain.name, num_users_main_domain)

        num_users_non_main_domain1 = random.randint(0, self.user_rate.monthly_limit // 2)
        generator.arbitrary_commcare_users_for_domain(self.non_main_domain1.name, num_users_non_main_domain1)

        self.addCleanup(self.cleanUpUser)

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)

        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('1200.0000'))
        user_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.USER)
        self.assertEqual(user_line_items.count(), 1)
        user_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.USER).first()
        self.assertEqual(user_line_item.quantity, 0)
        self.assertEqual(user_line_item.subtotal, Decimal('0.0000'))
        self.assertEqual(user_line_item.total, Decimal('0.0000'))
        self.assertIsNone(user_line_item.base_description)
        self.assertEqual(user_line_item.base_cost, Decimal('0.0000'))
        self.assertIsNone(user_line_item.unit_description)
        self.assertEqual(user_line_item.unit_cost, Decimal('1.0000'))

    def test_over_limit(self):
        num_users_main_domain = self.user_rate.monthly_limit + 1
        generator.arbitrary_commcare_users_for_domain(self.main_domain.name, num_users_main_domain)

        num_users_non_main_domain1 = self.user_rate.monthly_limit + 1
        generator.arbitrary_commcare_users_for_domain(self.non_main_domain1.name, num_users_non_main_domain1)

        self.addCleanup(self.cleanUpUser)

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)

        invoice = CustomerInvoice.objects.first()
        user_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.USER)
        self.assertEqual(user_line_items.count(), 1)
        user_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.USER).first()
        self.assertIsNone(user_line_item.base_description)
        self.assertEqual(user_line_item.base_cost, Decimal('0.0000'))
        num_to_charge = num_users_main_domain + num_users_non_main_domain1 - self.user_rate.monthly_limit
        self.assertEqual(num_to_charge, user_line_item.quantity)
        self.assertEqual(user_line_item.unit_cost, self.user_rate.per_excess_fee)
        self.assertEqual(user_line_item.total, self.user_rate.per_excess_fee * num_to_charge)
        self.assertEqual(user_line_item.subtotal, self.user_rate.per_excess_fee * num_to_charge)

    def test_balance_reflects_credit_deduction_for_account_level_user_credits(self):
        # Add User usage
        num_users_main_domain = self.user_rate.monthly_limit + 10
        generator.arbitrary_commcare_users_for_domain(self.main_domain.name, num_users_main_domain)
        num_users_non_main_domain1 = 1
        generator.arbitrary_commcare_users_for_domain(self.non_main_domain1.name, num_users_non_main_domain1)

        self.addCleanup(self.cleanUpUser)

        # Cover the cost of 1 User
        CreditLine.add_credit(
            amount=Decimal(1.0000),
            feature_type=FeatureType.USER,
            account=self.account,
        )

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        num_to_charge = num_users_main_domain + num_users_non_main_domain1 - self.user_rate.monthly_limit

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal(1200.0000) + num_to_charge - 1)

    # Comment out until subscription level bug is fixed
    # def test_balance_reflects_credit_deduction_for_multiple_subscription_level_user_credit(self):
    #     # Add User usage
    #     num_users_main_domain = self.user_rate.monthly_limit + 10
    #     generator.arbitrary_commcare_users_for_domain(self.main_domain.name, num_users_main_domain)
    #     num_users_non_main_domain1 = 10
    #     generator.arbitrary_commcare_users_for_domain(self.non_main_domain1.name, num_users_non_main_domain1)

    #     self.addCleanup(self.cleanUpUser)

    #     # Cover the cost of 2 User for main subscription
    #     CreditLine.add_credit(
    #         amount=Decimal(2.0000),
    #         feature_type=FeatureType.USER,
    #         subscription=self.main_subscription
    #     )

    #     # Cover the cost of 5 User for non main subscription 1
    #     CreditLine.add_credit(
    #         amount=Decimal(5.0000),
    #         feature_type=FeatureType.USER,
    #         subscription=self.non_main_sub1
    #     )

    #     num_to_charge = num_users_main_domain + num_users_non_main_domain1 - self.user_rate.monthly_limit

    #     calculate_users_in_all_domains(self.invoice_date)
    #     tasks.generate_invoices_based_on_date(self.invoice_date)
    #     self.assertEqual(CustomerInvoice.objects.count(), 1)
    #     invoice = CustomerInvoice.objects.first()
    #     self.assertEqual(invoice.balance, Decimal(1200.0000) + num_to_charge - 7)

    def test_balance_reflects_credit_deduction_for_single_subscription_level_user_credit(self):
        # Add User usage
        num_users_main_domain = self.user_rate.monthly_limit + 10
        generator.arbitrary_commcare_users_for_domain(self.main_domain.name, num_users_main_domain)
        num_users_non_main_domain1 = 1
        generator.arbitrary_commcare_users_for_domain(self.non_main_domain1.name, num_users_non_main_domain1)

        self.addCleanup(self.cleanUpUser)

        # Cover the cost of 2 User
        CreditLine.add_credit(
            amount=Decimal(2.0000),
            feature_type=FeatureType.USER,
            subscription=self.main_subscription
        )

        num_to_charge = num_users_main_domain + num_users_non_main_domain1 - self.user_rate.monthly_limit

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal(1200.0000) + num_to_charge - 2)


class TestSmsLineItem(BaseCustomerInvoiceCase):

    def setUp(self):
        super(TestSmsLineItem, self).setUp()
        self.sms_rate = self.main_subscription.plan_version.feature_rates.filter(
            feature__feature_type=FeatureType.SMS
        ).get()
        self.invoice_date = utils.get_first_day_x_months_later(
            self.main_subscription.date_start, random.randint(2, self.non_main_subscription_length)
        )
        self.sms_date = utils.get_first_day_x_months_later(self.invoice_date, -1)

    def tearDown(self):
        self._delete_sms_billables()
        super(TestSmsLineItem, self).tearDown()

    def test_under_limit(self):
        num_sms_main_domain = self.sms_rate.monthly_limit // 2
        arbitrary_sms_billables_for_domain(
            self.main_domain, self.sms_date, num_sms_main_domain, direction=INCOMING
        )
        num_sms_non_main_domain1 = self.sms_rate.monthly_limit // 2
        arbitrary_sms_billables_for_domain(
            self.non_main_domain1, self.sms_date, num_sms_non_main_domain1, direction=INCOMING
        )

        sms_line_items = self._create_sms_line_items()
        self.assertEqual(sms_line_items.count(), 1)
        for sms_line_item in sms_line_items:
            self.assertIsNone(sms_line_item.base_description)
            self.assertEqual(sms_line_item.base_cost, Decimal('0.0000'))
            self.assertEqual(sms_line_item.quantity, 1)
            self.assertEqual(sms_line_item.unit_cost, Decimal('0.0000'))
            self.assertIsNotNone(sms_line_item.unit_description)
            self.assertEqual(sms_line_item.subtotal, Decimal('0.0000'))
            self.assertEqual(sms_line_item.total, Decimal('0.0000'))

    def test_over_limit(self):
        num_sms_main_domain = random.randint(self.sms_rate.monthly_limit + 1, self.sms_rate.monthly_limit + 2)
        main_domain_billables = arbitrary_sms_billables_for_domain(
            self.main_domain, self.sms_date, num_sms_main_domain
        )
        num_sms_non_main_domain1 = random.randint(self.sms_rate.monthly_limit + 1,
                                          self.sms_rate.monthly_limit + 2)
        non_main_domain1_billables = arbitrary_sms_billables_for_domain(
            self.non_main_domain1, self.sms_date, num_sms_non_main_domain1
        )

        sms_line_items = self._create_sms_line_items()
        self.assertEqual(sms_line_items.count(), 1)
        for sms_line_item in sms_line_items:
            self.assertIsNone(sms_line_item.base_description)
            self.assertEqual(sms_line_item.base_cost, Decimal('0.0000'))
            self.assertEqual(sms_line_item.quantity, 1)

            sms_cost = sum(
                billable.gateway_charge + billable.usage_charge
                for billable in (
                    non_main_domain1_billables[self.sms_rate.monthly_limit:]
                    + main_domain_billables
                ))
            self.assertEqual(sms_line_item.unit_cost, sms_cost)
            self.assertEqual(sms_line_item.total, sms_cost)

    # Comment out until subscription level credit bug is fixed
    # def test_balance_reflects_credit_deduction_for_multiple_subscription_level_sms_credits(self):
    #     # Add SMS usage
    #     arbitrary_sms_billables_for_domain(
    #         self.main_domain, self.sms_date, self.sms_rate.monthly_limit + 1
    #     )
    #     arbitrary_sms_billables_for_domain(
    #         self.non_main_domain1, self.sms_date, num_sms=10
    #     )

    #     # Cover the cost of 1 SMS for main subscription
    #     CreditLine.add_credit(
    #         amount=Decimal(0.7500),
    #         feature_type=FeatureType.SMS,
    #         subscription=self.main_subscription
    #     )

    #     # Cover the cost of 1 SMS for non main subscription 1
    #     CreditLine.add_credit(
    #         amount=Decimal(0.7500),
    #         feature_type=FeatureType.SMS,
    #         subscription=self.non_main_sub1
    #     )

    #     calculate_users_in_all_domains(self.invoice_date)
    #     tasks.generate_invoices_based_on_date(self.invoice_date)
    #     self.assertEqual(CustomerInvoice.objects.count(), 1)
    #     invoice = CustomerInvoice.objects.first()
    #     self.assertEqual(invoice.balance, Decimal('1206.7500'))

    def test_balance_reflects_credit_deduction_for_single_subscription_level_sms_credits(self):
        # Add SMS usage
        arbitrary_sms_billables_for_domain(
            self.main_domain, self.sms_date, self.sms_rate.monthly_limit + 1
        )
        arbitrary_sms_billables_for_domain(
            self.non_main_domain1, self.sms_date, num_sms=10
        )

        # Cover the cost of 1 SMS
        CreditLine.add_credit(
            amount=Decimal(0.7500),
            feature_type=FeatureType.SMS,
            subscription=self.main_subscription
        )

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('1207.5000'))

    def test_balance_reflects_credit_deduction_for_account_level_sms_credits(self):
        # Add SMS usage
        arbitrary_sms_billables_for_domain(
            self.main_domain, self.sms_date, self.sms_rate.monthly_limit + 1
        )
        arbitrary_sms_billables_for_domain(
            self.non_main_domain1, self.sms_date, num_sms=10
        )

        # Cover the cost of 1 SMS
        CreditLine.add_credit(
            amount=Decimal(0.7500),
            feature_type=FeatureType.SMS,
            account=self.account,
        )

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.balance, Decimal('1207.5000'))

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
        self.user_rate = self.main_subscription.plan_version.feature_rates \
            .filter(feature__feature_type=FeatureType.USER).get()
        self.initialize_domain_user_history_objects()
        self.sms_rate = self.main_subscription.plan_version.feature_rates.filter(
            feature__feature_type=FeatureType.SMS
        ).get()
        self.invoice_date = utils.get_first_day_x_months_later(
            self.main_subscription.date_start, random.randint(3, self.non_main_subscription_length)
        )
        self.sms_date = utils.get_first_day_x_months_later(self.invoice_date, -1)

    def initialize_domain_user_history_objects(self):
        record_dates = []
        month_end = self.main_subscription.date_end
        while month_end > self.main_subscription.date_start:
            record_dates.append(month_end)
            _, month_end = get_previous_month_date_range(month_end)

        self.num_users = self.user_rate.monthly_limit + 1
        for record_date in record_dates:
            DomainUserHistory.objects.create(
                domain=self.main_domain,
                num_users=self.num_users,
                record_date=record_date
            )

        for record_date in record_dates:
            DomainUserHistory.objects.create(
                domain=self.non_main_domain1,
                num_users=self.num_users,
                record_date=record_date
            )

        for record_date in record_dates:
            DomainUserHistory.objects.create(
                domain=self.non_main_domain2,
                num_users=0,
                record_date=record_date
            )

    def test_user_over_limit_in_quarterly_invoice(self):
        self.account.invoicing_plan = InvoicingPlan.QUARTERLY
        self.account.save()
        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)

        invoice = CustomerInvoice.objects.first()
        user_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.USER)
        num_excess_users_quarterly = (self.num_users * 2 - self.user_rate.monthly_limit) * 3
        self.assertEqual(user_line_items.count(), 1)
        for user_line_item in user_line_items:
            self.assertEqual(user_line_item.quantity, num_excess_users_quarterly)

    def test_user_over_limit_in_yearly_invoice(self):
        self.account.invoicing_plan = InvoicingPlan.YEARLY
        self.account.save()
        invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start, 14)
        tasks.generate_invoices_based_on_date(invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)

        invoice = CustomerInvoice.objects.first()
        user_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.USER)
        num_excess_users_quarterly = (self.num_users * 2 - self.user_rate.monthly_limit) * 12
        self.assertEqual(user_line_items.count(), 1)
        for user_line_item in user_line_items:
            self.assertEqual(user_line_item.quantity, num_excess_users_quarterly)

    def test_sms_over_limit_in_quarterly_invoice(self):
        num_sms = random.randint(self.sms_rate.monthly_limit + 1, self.sms_rate.monthly_limit + 2)
        billables_main_domain = arbitrary_sms_billables_for_domain(
            self.main_domain, self.sms_date, num_sms
        )
        billables_non_main_domain1 = arbitrary_sms_billables_for_domain(
            self.non_main_domain1, self.sms_date, num_sms
        )

        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()

        sms_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.SMS)
        self.assertEqual(sms_line_items.count(), 1)
        for sms_line_item in sms_line_items:
            self.assertIsNone(sms_line_item.base_description)
            self.assertEqual(sms_line_item.base_cost, Decimal('0.0000'))
            self.assertEqual(sms_line_item.quantity, 1)

            sms_cost = sum(
                billable.gateway_charge + billable.usage_charge
                for billable in (
                    billables_non_main_domain1[self.sms_rate.monthly_limit:]
                    + billables_main_domain
                ))
            self.assertEqual(sms_line_item.unit_cost, sms_cost)
            self.assertEqual(sms_line_item.total, sms_cost)

    def test_sms_over_limit_in_yearly_invoice(self):
        num_sms = random.randint(self.sms_rate.monthly_limit + 1, self.sms_rate.monthly_limit + 2)
        billables_main_domain = arbitrary_sms_billables_for_domain(
            self.main_domain, self.sms_date, num_sms
        )
        billables_non_main_domain1 = arbitrary_sms_billables_for_domain(
            self.non_main_domain1, self.sms_date, num_sms
        )

        tasks.generate_invoices_based_on_date(self.invoice_date)
        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()

        sms_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.SMS)
        self.assertEqual(sms_line_items.count(), 1)
        for sms_line_item in sms_line_items:
            self.assertIsNone(sms_line_item.base_description)
            self.assertEqual(sms_line_item.base_cost, Decimal('0.0000'))
            self.assertEqual(sms_line_item.quantity, 1)

            sms_cost = sum(
                billable.gateway_charge + billable.usage_charge
                for billable in (
                    billables_non_main_domain1[self.sms_rate.monthly_limit:]
                    + billables_main_domain
                ))
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


class TestCustomerInvoiceGenerationIsAtomic(BaseCustomerInvoiceCase):

    def setUp(self):
        super().setUp()
        from corehq.apps.accounting.models import Feature, FeatureRate
        web_user_feature, __ = Feature.objects.get_or_create(
            name="Web User", defaults={"feature_type": FeatureType.WEB_USER})
        self.web_user_rate = FeatureRate.objects.create(
            feature=web_user_feature,
            monthly_fee=Decimal('0.00'),
            monthly_limit=1,
            per_excess_fee=Decimal('10.00'),
        )
        self.main_subscription.plan_version.feature_rates.add(self.web_user_rate)
        self.account.bill_web_user = True
        self.account.save()
        self.invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start, 5)
        # The default ADVANCED test plan also carries a USER feature rate, so
        # invoice generation needs a DomainUserHistory snapshot to succeed at
        # all (independent of the web-user feature under test).
        calculate_users_in_all_domains(self.invoice_date)

    def test_missing_web_user_snapshot_rolls_back_partial_invoice(self):
        """WebUserLineItemFactory.total_users_for_date raises DoesNotExist
        when the account's BillingAccountWebUserHistory for a month is
        missing. Invoice generation must be atomic: the whole invoice rolls
        back rather than leaving a partial CustomerInvoice row. The task
        catches per-account exceptions, so assert on DB state rather than on
        a raised error."""
        # Deliberately no BillingAccountWebUserHistory snapshot created.
        tasks.generate_invoices_based_on_date(self.invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 0)


class TestBillingAccountDomainHistory(BaseCustomerInvoiceCase):

    def test_unique_per_account_and_date(self):
        from django.db import IntegrityError, transaction
        from corehq.apps.accounting.models import BillingAccountDomainHistory
        record_date = date(2016, 5, 31)
        BillingAccountDomainHistory.objects.create(
            billing_account=self.account, record_date=record_date, num_domains=3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BillingAccountDomainHistory.objects.create(
                billing_account=self.account, record_date=record_date, num_domains=4)


class TestCalculateDomainsInAllBillingAccounts(BaseCustomerInvoiceCase):

    def setUp(self):
        super().setUp()
        # get_domains() filters on is_active=True, which is wall-clock state.
        # The generator creates subscriptions with is_active=False (its
        # default), so activate them to simulate live subscriptions.
        Subscription.visible_and_suppressed_objects.filter(account=self.account).update(is_active=True)

    def test_snapshots_active_domain_count_for_customer_account(self):
        from corehq.apps.accounting.models import BillingAccountDomainHistory
        from corehq.apps.accounting.tasks import calculate_domains_in_all_billing_accounts

        # BaseCustomerInvoiceCase sets up 3 subscriptions (main + 2 non-main)
        # on a single customer account.
        today = date(2016, 6, 1)
        calculate_domains_in_all_billing_accounts(today)

        history = BillingAccountDomainHistory.objects.get(
            billing_account=self.account, record_date=date(2016, 5, 31))
        self.assertEqual(history.num_domains, 3)

    def test_skips_non_customer_accounts(self):
        from corehq.apps.accounting.models import BillingAccountDomainHistory
        from corehq.apps.accounting.tasks import calculate_domains_in_all_billing_accounts

        self.account.is_customer_billing_account = False
        self.account.save()
        calculate_domains_in_all_billing_accounts(date(2016, 6, 1))

        self.assertEqual(BillingAccountDomainHistory.objects.count(), 0)


class TestDomainLineItem(BaseCustomerInvoiceCase):

    is_using_test_plans = True

    def setUp(self):
        super().setUp()
        # get_domains() filters on is_active=True (wall-clock state); the
        # generator's default is is_active=False, so activate the snapshot
        # source. Invoice generation itself selects by date overlap.
        Subscription.visible_and_suppressed_objects.filter(account=self.account).update(is_active=True)
        self.domain_rate = self.add_domain_feature_rate(
            monthly_limit=1,                 # included-domains allowance
            per_excess_fee=Decimal('100.00'),
        )
        # Fixed mid-life month so all three subscriptions span the full
        # invoice month (no proration).
        self.invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start, 5)
        # The default ADVANCED test plan also carries a USER feature rate, so
        # invoice generation needs a DomainUserHistory snapshot to succeed at
        # all (independent of the Domain feature under test); without it,
        # invoice generation raises and is swallowed as a logged [BILLING]
        # error, silently producing zero line items and masking assertions.
        calculate_users_in_all_domains(self.invoice_date)

    def test_over_allowance_charges_per_excess_domain(self):
        from corehq.apps.accounting.tasks import calculate_domains_in_all_billing_accounts
        calculate_domains_in_all_billing_accounts(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        invoice = CustomerInvoice.objects.first()
        domain_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.DOMAIN)
        self.assertEqual(domain_line_items.count(), 1)
        domain_line_item = domain_line_items.first()
        # 3 active domains - allowance of 1 = 2 excess
        self.assertEqual(domain_line_item.quantity, 2)
        self.assertEqual(domain_line_item.unit_cost, Decimal('100.00'))
        self.assertEqual(domain_line_item.total, Decimal('200.00'))

    def test_unlimited_monthly_limit_charges_nothing(self):
        from corehq.apps.accounting.models import UNLIMITED_FEATURE_USAGE
        from corehq.apps.accounting.tasks import calculate_domains_in_all_billing_accounts
        self.domain_rate.monthly_limit = UNLIMITED_FEATURE_USAGE
        self.domain_rate.save()
        calculate_domains_in_all_billing_accounts(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        invoice = CustomerInvoice.objects.first()
        domain_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.DOMAIN).first()
        self.assertEqual(domain_line_item.quantity, 0)
        self.assertEqual(domain_line_item.total, Decimal('0.0000'))

    def test_domain_line_item_in_quarterly_invoice(self):
        from corehq.apps.accounting.models import BillingAccountDomainHistory
        self.account.invoicing_plan = InvoicingPlan.QUARTERLY
        self.account.save()
        invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start, 14)
        # Quarterly invoicing sums excess domains over the three month-ends
        # in the quarter: 2017-01-31, 2017-02-28, 2017-03-31 (record_date is
        # always the day before the snapshot task's "today", as in
        # calculate_domains_in_all_billing_accounts).
        for months_before_invoice_date, num_domains in zip(range(3), [2, 3, 5]):
            user_date = date(invoice_date.year, invoice_date.month, 1)
            user_date -= relativedelta.relativedelta(months=months_before_invoice_date)
            calculate_users_in_all_domains(user_date)
            record_date = user_date - relativedelta.relativedelta(days=1)
            BillingAccountDomainHistory.objects.create(
                billing_account=self.account, record_date=record_date, num_domains=num_domains)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        domain_line_items = invoice.lineitem_set.get_feature_by_type(FeatureType.DOMAIN)
        self.assertEqual(domain_line_items.count(), 1)
        domain_line_item = domain_line_items.first()
        # allowance of 1: (2-1) + (3-1) + (5-1) = 1 + 2 + 4 = 7
        self.assertEqual(domain_line_item.quantity, 7)
        self.assertEqual(domain_line_item.unit_cost, Decimal('100.00'))
        self.assertEqual(domain_line_item.total, Decimal('700.00'))

    def test_missing_snapshot_charges_zero_excess(self):
        """Before a DOMAIN feature rate exists on a plan, there is no concept
        of an excess domain at all -- the account is just billed the flat
        product fee. A missing BillingAccountDomainHistory snapshot (e.g. the
        cold-start window right after a Domain rate is first attached, before
        monthly snapshots have accumulated) must be treated the same way: as
        zero excess domains for that month, not as a hard failure that blocks
        the entire invoice."""
        # Deliberately no calculate_domains_in_all_billing_accounts run.
        tasks.generate_invoices_based_on_date(self.invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 1)
        invoice = CustomerInvoice.objects.first()
        domain_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.DOMAIN).first()
        self.assertEqual(domain_line_item.quantity, 0)
        self.assertEqual(domain_line_item.total, Decimal('0.0000'))

    def test_within_allowance_charges_nothing(self):
        from corehq.apps.accounting.tasks import calculate_domains_in_all_billing_accounts
        self.domain_rate.monthly_limit = 10
        self.domain_rate.save()
        calculate_domains_in_all_billing_accounts(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        invoice = CustomerInvoice.objects.first()
        domain_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.DOMAIN).first()
        self.assertEqual(domain_line_item.quantity, 0)
        self.assertEqual(domain_line_item.total, Decimal('0.0000'))

    def test_no_domain_line_item_without_domain_rate(self):
        from corehq.apps.accounting.tasks import calculate_domains_in_all_billing_accounts
        self.main_subscription.plan_version.feature_rates.remove(self.domain_rate)
        calculate_domains_in_all_billing_accounts(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        invoice = CustomerInvoice.objects.first()
        self.assertEqual(invoice.lineitem_set.get_feature_by_type(FeatureType.DOMAIN).count(), 0)

    def test_domain_rate_on_non_customer_account_is_skipped(self):
        """A Domain rate on a non-customer plan must not crash regular
        invoicing (snapshots only exist for customer accounts) — the guard in
        generate_line_items skips the factory entirely."""
        from unittest.mock import patch
        from corehq.apps.accounting.models import Invoice
        # self.account is the class-level fixture shared across this test
        # class's methods; restore it so later tests still see a customer
        # account (Django's TestCase rolls back the DB row, but not this
        # Python attribute mutation).
        self.addCleanup(setattr, self.account, 'is_customer_billing_account', True)
        self.account.is_customer_billing_account = False
        self.account.save()
        # setUp() already ran calculate_users_in_all_domains, so regular
        # invoices have the user-count snapshot for their USER line item;
        # the only missing history is the domain one.
        # No domain snapshot task run: without the guard this would raise
        # BillingAccountDomainHistory.DoesNotExist during invoice generation.
        # The PDF footer reverses a domain-scoped URL, which doesn't match
        # the base fixture's domain names (e.g. "main domain" contains a
        # space); that's incidental to what's under test here, so stub it out.
        with patch('corehq.apps.accounting.invoice_pdf.absolute_reverse', return_value='http://example.com'):
            tasks.generate_invoices_based_on_date(self.invoice_date)

        self.assertEqual(CustomerInvoice.objects.count(), 0)
        invoice = Invoice.objects.filter(subscription=self.main_subscription).first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.lineitem_set.get_feature_by_type(FeatureType.DOMAIN).count(), 0)

    def test_get_feature_name_does_not_raise(self):
        from corehq.apps.accounting.user_text import get_feature_name
        self.assertEqual(get_feature_name(FeatureType.DOMAIN), "Project Spaces")

    def test_user_facing_description_with_domain_rate(self):
        # Regression: FEATURE_TYPE_TO_NAME lookup in user_facing_description
        # used to KeyError for a plan version carrying a Domain feature rate.
        description = self.main_subscription.plan_version.user_facing_description
        domain_rates = [r for r in description['rates'] if r['name'] == "Project Spaces"]
        self.assertEqual(len(domain_rates), 1)
        self.assertEqual(domain_rates[0]['included'], self.domain_rate.monthly_limit)

    def test_usage_calculator_returns_active_domain_count_for_account(self):
        from corehq.apps.accounting.usage import FeatureUsageCalculator
        # get_active_subscription_by_domain is quickcache'd; the fixture's
        # activation of subscriptions uses a bulk .update() (bypasses .save(),
        # so it never invalidates this cache). Clear it after populating so a
        # stale cached Subscription doesn't leak into sibling tests / the
        # class's domain-deletion teardown.
        self.addCleanup(Subscription._get_active_subscription_by_domain.clear,
                         Subscription, self.main_domain.name)
        calc = FeatureUsageCalculator(self.domain_rate, self.main_domain.name)
        # BaseCustomerInvoiceCase sets up 3 active domains on the account.
        self.assertEqual(calc.get_usage(), 3)

    def test_usage_calculator_returns_zero_without_active_subscription(self):
        from corehq.apps.accounting.usage import FeatureUsageCalculator
        calc = FeatureUsageCalculator(self.domain_rate, "domain-with-no-subscription")
        self.assertEqual(calc.get_usage(), 0)


class TestBundledFeatureUnit(TestCase):
    """A BundledFeatureUnit row bundles units of another feature type into
    each unit of the carrier rate's feature (spec §2a)."""

    def _domain_rate(self, units=()):
        from corehq.apps.accounting.models import BundledFeatureUnit, Feature, FeatureRate
        feature, __ = Feature.objects.get_or_create(
            name="Domain", defaults={"feature_type": FeatureType.DOMAIN})
        rate = FeatureRate.objects.create(
            feature=feature, monthly_limit=1, per_excess_fee=Decimal('100.00'))
        for feature_type, quantity in units:
            BundledFeatureUnit.objects.create(
                feature_rate=rate, feature_type=feature_type, quantity_per_unit=quantity)
        return rate

    def test_unit_change_registers_as_rate_change(self):
        # __eq__ drives _retrieve_feature_rate's is-this-a-new-rate decision
        # when a plan version is edited; a bundling change must produce a new
        # immutable rate row. The form stashes not-yet-saved units on the
        # instance as _pending_bundled_units.
        from corehq.apps.accounting.models import FeatureRate
        current = self._domain_rate(units=[(FeatureType.USER, 100)])
        edited_same = FeatureRate(
            feature=current.feature, monthly_limit=1, per_excess_fee=Decimal('100.00'))
        edited_same._pending_bundled_units = [(FeatureType.USER, 100)]
        edited_qty = FeatureRate(
            feature=current.feature, monthly_limit=1, per_excess_fee=Decimal('100.00'))
        edited_qty._pending_bundled_units = [(FeatureType.USER, 150)]
        edited_removed = FeatureRate(
            feature=current.feature, monthly_limit=1, per_excess_fee=Decimal('100.00'))
        edited_removed._pending_bundled_units = []

        self.assertEqual(current, edited_same)
        self.assertNotEqual(current, edited_qty)
        self.assertNotEqual(current, edited_removed)

    def test_units_rejected_on_non_domain_carrier(self):
        from django.core.exceptions import ValidationError
        from corehq.apps.accounting.models import BundledFeatureUnit, Feature, FeatureRate
        user_feature = Feature.objects.create(name="User carrier test", feature_type=FeatureType.USER)
        user_rate = FeatureRate.objects.create(feature=user_feature)
        unit = BundledFeatureUnit(
            feature_rate=user_rate, feature_type=FeatureType.USER, quantity_per_unit=100)
        with self.assertRaises(ValidationError):
            unit.full_clean()

    def test_non_user_unit_type_rejected(self):
        from django.core.exceptions import ValidationError
        from corehq.apps.accounting.models import BundledFeatureUnit
        rate = self._domain_rate()
        unit = BundledFeatureUnit(
            feature_rate=rate, feature_type=FeatureType.SMS, quantity_per_unit=500)
        with self.assertRaises(ValidationError):
            unit.full_clean()

    def test_user_unit_on_domain_carrier_is_valid(self):
        from corehq.apps.accounting.models import BundledFeatureUnit
        rate = self._domain_rate()
        unit = BundledFeatureUnit(
            feature_rate=rate, feature_type=FeatureType.USER, quantity_per_unit=100)
        unit.full_clean()  # no error

    def test_form_round_trips_bundled_mobile_workers(self):
        from corehq.apps.accounting.forms import FeatureRateForm
        from corehq.apps.accounting.utils import fmt_feature_rate_dict
        rate = self._domain_rate(units=[(FeatureType.USER, 100)])
        self.assertEqual(
            fmt_feature_rate_dict(rate.feature, rate)['bundled_mobile_workers'], 100)

        form = FeatureRateForm({
            'feature_id': rate.feature.id,
            'monthly_fee': '0.00',
            'monthly_limit': 1,
            'per_excess_fee': '100.00',
            'bundled_mobile_workers': 150,
        })
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.get_instance(rate.feature)
        self.assertEqual(instance._pending_bundled_units, [(FeatureType.USER, 150)])
        instance.save()
        instance.save_pending_bundled_units()
        self.assertEqual(
            instance.bundled_units.get(feature_type=FeatureType.USER).quantity_per_unit,
            150)

    def test_form_rejects_bundled_workers_on_non_domain_rates(self):
        from corehq.apps.accounting.forms import FeatureRateForm
        from corehq.apps.accounting.models import Feature
        user_feature = Feature.objects.create(name="User form test", feature_type=FeatureType.USER)
        form = FeatureRateForm({
            'feature_id': user_feature.id,
            'monthly_fee': '0.00',
            'monthly_limit': 10,
            'per_excess_fee': '1.00',
            'bundled_mobile_workers': 5,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('bundled_mobile_workers', form.errors)


class TestBundledUserAllowance(BaseCustomerInvoiceCase):
    """Every project space bundles the DOMAIN rate's USER-type unit quantity
    into the plan's effective mobile-worker limit (spec §6a, every-bundle
    semantics): effective_limit(m) = base + num_domains(m) × N."""

    is_using_test_plans = True

    def setUp(self):
        super().setUp()
        Subscription.visible_and_suppressed_objects.filter(account=self.account).update(is_active=True)
        self.domain_rate = self.add_domain_feature_rate(
            monthly_limit=1,
            per_excess_fee=Decimal('100.00'),
            bundled_mobile_workers=5,
        )
        self.user_rate = self.main_subscription.plan_version.feature_rates \
            .filter(feature__feature_type=FeatureType.USER).get()
        self.invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start, 5)
        self.month_end = self.invoice_date - relativedelta.relativedelta(days=1)

    def _create_user_histories(self, month_end, num_users_main_domain):
        # The USER factory sums DomainUserHistory across all subscribed
        # domains and raises on a missing row; put all usage on main domain.
        for domain_obj in [self.main_domain, self.non_main_domain1, self.non_main_domain2]:
            num_users = num_users_main_domain if domain_obj is self.main_domain else 0
            DomainUserHistory.objects.create(
                domain=domain_obj.name, record_date=month_end, num_users=num_users)

    def _snapshot_domains(self, month_end, num_domains):
        from corehq.apps.accounting.models import BillingAccountDomainHistory
        BillingAccountDomainHistory.objects.create(
            billing_account=self.account, record_date=month_end, num_domains=num_domains)

    def _user_line_item(self):
        invoice = CustomerInvoice.objects.first()
        return invoice.lineitem_set.get_feature_by_type(FeatureType.USER).first()

    def test_bundled_units_raise_user_limit(self):
        base = self.user_rate.monthly_limit
        # every-bundle: 3 domains x 5 = +15 included users
        self._snapshot_domains(self.month_end, 3)
        self._create_user_histories(self.month_end, base + 17)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        user_line_item = self._user_line_item()
        self.assertEqual(user_line_item.quantity, 2)
        self.assertEqual(user_line_item.unit_cost, self.user_rate.per_excess_fee)

    def test_no_bundling_without_unit_row(self):
        from corehq.apps.accounting.models import BundledFeatureUnit
        BundledFeatureUnit.objects.filter(feature_rate=self.domain_rate).delete()
        base = self.user_rate.monthly_limit
        self._snapshot_domains(self.month_end, 3)
        self._create_user_histories(self.month_end, base + 17)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        self.assertEqual(self._user_line_item().quantity, 17)

    def test_missing_domain_snapshot_uses_base_limit(self):
        base = self.user_rate.monthly_limit
        self._create_user_histories(self.month_end, base + 17)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        self.assertEqual(self._user_line_item().quantity, 17)

    def test_unlimited_domain_rate_still_bundles(self):
        # Unlimited project spaces means no per-space CHARGE, but under
        # every-bundle semantics each space still carries its bundled users.
        from corehq.apps.accounting.models import UNLIMITED_FEATURE_USAGE
        self.domain_rate.monthly_limit = UNLIMITED_FEATURE_USAGE
        self.domain_rate.save()
        base = self.user_rate.monthly_limit
        self._snapshot_domains(self.month_end, 3)
        self._create_user_histories(self.month_end, base + 17)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        self.assertEqual(self._user_line_item().quantity, 2)
        invoice = CustomerInvoice.objects.first()
        domain_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.DOMAIN).first()
        self.assertEqual(domain_line_item.quantity, 0)

    def test_web_user_line_item_unaffected_by_bundling(self):
        from corehq.apps.accounting.models import (
            BillingAccountWebUserHistory,
            Feature,
            FeatureRate,
        )
        web_feature, __ = Feature.objects.get_or_create(
            name="Web User", defaults={"feature_type": FeatureType.WEB_USER})
        web_rate = FeatureRate.objects.create(
            feature=web_feature, monthly_limit=1, per_excess_fee=Decimal('10.00'))
        self.main_subscription.plan_version.feature_rates.add(web_rate)
        self.addCleanup(setattr, self.account, 'bill_web_user', self.account.bill_web_user)
        self.account.bill_web_user = True
        self.account.save()
        # 3 domains would grant +15 if the bundling wrongly applied here
        self._snapshot_domains(self.month_end, 3)
        BillingAccountWebUserHistory.objects.create(
            billing_account=self.account, record_date=self.month_end, num_users=4)
        self._create_user_histories(self.month_end, 0)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        invoice = CustomerInvoice.objects.first()
        web_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.WEB_USER).first()
        self.assertEqual(web_line_item.quantity, 3)

    def test_quarterly_effective_limit_varies_by_month(self):
        # self.account is the shared class-level fixture; Django's rollback
        # undoes the DB write but not this in-memory attribute mutation, and a
        # later test's account.save() would re-persist it.
        self.addCleanup(setattr, self.account, 'invoicing_plan', self.account.invoicing_plan)
        self.account.invoicing_plan = InvoicingPlan.QUARTERLY
        self.account.save()
        invoice_date = utils.get_first_day_x_months_later(self.main_subscription.date_start, 14)
        base = self.user_rate.monthly_limit
        # Domain counts 1, 3, 5 over the quarter's month-ends give bundled
        # allowances of +5, +15, +25 against a constant base+15 users each
        # month: excesses 10, 0, 0 -> summed quantity 10.
        for months_before_invoice_date, num_domains in zip(range(3), [1, 3, 5]):
            first_of_month = date(invoice_date.year, invoice_date.month, 1)
            first_of_month -= relativedelta.relativedelta(months=months_before_invoice_date)
            month_end = first_of_month - relativedelta.relativedelta(days=1)
            self._snapshot_domains(month_end, num_domains)
            self._create_user_histories(month_end, base + 15)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(self._user_line_item().quantity, 10)
        invoice = CustomerInvoice.objects.first()
        domain_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.DOMAIN).first()
        # the charge is still excess-only: 0 + 2 + 4
        self.assertEqual(domain_line_item.quantity, 6)

    def test_user_line_item_description_shows_effective_limit(self):
        base = self.user_rate.monthly_limit
        self._snapshot_domains(self.month_end, 3)
        self._create_user_histories(self.month_end, base + 17)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        description = self._user_line_item().unit_description
        # every-bundle: 3 domains x 5 bundled users raise the displayed limit
        self.assertIn("plan limit of %d" % (base + 15), description)

    def test_domain_line_item_description_mentions_bundled_users(self):
        base = self.user_rate.monthly_limit
        self._snapshot_domains(self.month_end, 3)
        self._create_user_histories(self.month_end, base)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        invoice = CustomerInvoice.objects.first()
        domain_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.DOMAIN).first()
        self.assertIn("project space", domain_line_item.unit_description)
        self.assertIn("Each project space includes 5 mobile workers",
                      domain_line_item.unit_description)

    def test_effective_limit_helper_for_subscription_page(self):
        from corehq.apps.domain.views.accounting import get_effective_feature_limit
        plan_version = self.main_subscription.plan_version
        # 3 live active domains x 5 bundled users -> base + 15 (every-bundle)
        self.assertEqual(
            get_effective_feature_limit(plan_version, self.user_rate, self.account),
            self.user_rate.monthly_limit + 15)
        # non-USER rates and missing account fall back to the static limit
        self.assertEqual(
            get_effective_feature_limit(plan_version, self.domain_rate, self.account),
            self.domain_rate.monthly_limit)
        self.assertEqual(
            get_effective_feature_limit(plan_version, self.user_rate, None),
            self.user_rate.monthly_limit)
