import datetime
import random
from decimal import Decimal

from django.conf import settings
from django.core import mail
from django.test import override_settings

from dimagi.utils.dates import add_months_to_date

from corehq.apps.accounting import tasks, utils
from corehq.apps.accounting.invoicing import DomainInvoiceFactory
from corehq.apps.accounting.models import (
    SMALL_INVOICE_THRESHOLD,
    BillingAccount,
    BillingRecord,
    DefaultProductPlan,
    FeatureType,
    Invoice,
    SoftwarePlanEdition,
    Subscriber,
    SubscriptionType,
)
from corehq.apps.accounting.tasks import calculate_users_in_all_domains
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
from corehq.apps.smsbillables.tests.generator import (
    arbitrary_sms_billables_for_domain,
)
from corehq.apps.users.models import WebUser


class BaseInvoiceTestCase(BaseAccountingTest):

    is_using_test_plans = False
    min_subscription_length = 3
    is_testing_web_user_feature = False

    @classmethod
    def setUpClass(cls):
        super(BaseInvoiceTestCase, cls).setUpClass()

        if cls.is_using_test_plans:
            generator.bootstrap_test_software_plan_versions()

        cls.billing_contact = generator.create_arbitrary_web_user_name()
        cls.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        cls.currency = generator.init_default_currency()
        cls.account = generator.billing_account(
            cls.dimagi_user, cls.billing_contact)
        cls.domain = generator.arbitrary_domain()

        cls.subscription_length = 15  # months
        subscription_start_date = datetime.date(2016, 2, 23)
        cls.subscription_is_active = False
        if cls.is_testing_web_user_feature:
            # make sure the subscription is still active when we count web users
            cls.subscription_is_active = True
        subscription_end_date = add_months_to_date(subscription_start_date, cls.subscription_length)
        cls.subscription = generator.generate_domain_subscription(
            cls.account,
            cls.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
            is_active=cls.subscription_is_active
        )

    def tearDown(self):
        for user in self.domain.all_users():
            user.delete(self.domain.name, deleted_by=None)
        super(BaseAccountingTest, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()

        if cls.is_using_test_plans:
            utils.clear_plan_version_cache()

        super(BaseInvoiceTestCase, cls).tearDownClass()


class TestInvoice(BaseInvoiceTestCase):
    """
    Tests that invoices are properly generated for the first month, last month, and a random month in the middle
    of a subscription for a domain.
    """

    def test_no_invoice_before_start(self):
        """
        No invoice gets created if the subscription didn't start in the previous month.
        """
        tasks.generate_invoices_based_on_date(self.subscription.date_start)
        self.assertEqual(self.subscription.invoice_set.count(), 0)

    def test_subscription_invoice(self):
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        self.assertEqual(self.subscription.invoice_set.count(), 1)
        self.assertEqual(self.subscription.subscriber.domain, self.domain.name)

        invoice = self.subscription.invoice_set.latest('date_created')

        num_product_line_items = invoice.lineitem_set.get_products().count()
        self.assertEqual(num_product_line_items, 1)

        num_feature_line_items = invoice.lineitem_set.get_features().count()
        self.assertEqual(num_feature_line_items, self.subscription.plan_version.feature_rates.count())
        self.assertEqual(invoice.subscription, self.subscription)
        self.assertGreater(invoice.balance, Decimal('0.0000'))

    def test_no_invoice_after_end(self):
        """
        No invoices should be generated for the months after the end date of the subscription.
        """
        invoice_date = utils.months_from_date(self.subscription.date_end, 2)
        tasks.generate_invoices_based_on_date(invoice_date)
        self.assertEqual(self.subscription.invoice_set.count(), 0)

    def test_community_no_charges_no_invoice(self):
        """
        No invoices should be generated for domains that are not on a subscription and do not
        have any per_excess charges on users or SMS messages
        """
        domain = generator.arbitrary_domain()
        self.addCleanup(domain.delete)
        tasks.generate_invoices_based_on_date(datetime.date.today())
        self.assertRaises(Invoice.DoesNotExist,
                          lambda: Invoice.objects.get(subscription__subscriber__domain=domain.name))

    def test_community_invoice(self):
        """
        For an unsubscribed domain with any charges over the community limit for the month of invoicing,
        make sure that an invoice is generated in addition to a subscription for that month to
        the community plan.
        """
        domain = generator.arbitrary_domain()
        self.addCleanup(domain.delete)
        generator.create_excess_community_users(domain)
        account = BillingAccount.get_or_create_account_by_domain(
            domain, created_by=self.dimagi_user)[0]
        generator.arbitrary_contact_info(account, self.dimagi_user)
        account.date_confirmed_extra_charges = datetime.date.today()
        account.save()
        today = datetime.date.today()
        calculate_users_in_all_domains(datetime.date(today.year, today.month, 1))
        tasks.generate_invoices_based_on_date(today)
        subscriber = Subscriber.objects.get(domain=domain.name)
        invoices = Invoice.objects.filter(subscription__subscriber=subscriber)
        self.assertEqual(invoices.count(), 1)
        invoice = invoices.get()
        self.assertEqual(invoice.subscription.subscriber.domain, domain.name)
        self.assertEqual(invoice.subscription.date_start, invoice.date_start)
        self.assertEqual(
            invoice.subscription.date_end - datetime.timedelta(days=1),
            invoice.date_end
        )

    def test_date_due_not_set_small_invoice(self):
        """Date Due doesn't get set if the invoice is small"""
        invoice_date_small = utils.months_from_date(self.subscription.date_start, 1)
        calculate_users_in_all_domains(invoice_date_small)
        tasks.generate_invoices_based_on_date(invoice_date_small)
        small_invoice = self.subscription.invoice_set.first()

        self.assertTrue(small_invoice.balance <= SMALL_INVOICE_THRESHOLD)
        self.assertIsNone(small_invoice.date_due)

    def test_date_due_set_large_invoice(self):
        """Date Due only gets set for a large invoice (> $100)"""
        self.subscription.plan_version = generator.subscribable_plan_version(SoftwarePlanEdition.ADVANCED)
        self.subscription.save()
        invoice_date_large = utils.months_from_date(self.subscription.date_start, 3)
        calculate_users_in_all_domains(invoice_date_large)
        tasks.generate_invoices_based_on_date(invoice_date_large)
        large_invoice = self.subscription.invoice_set.last()

        self.assertTrue(large_invoice.balance > SMALL_INVOICE_THRESHOLD)
        self.assertIsNotNone(large_invoice.date_due)

    def test_date_due_gets_set_autopay(self):
        """Date due always gets set for autopay """
        self.subscription.account.update_autopay_user(self.billing_contact, self.domain)
        invoice_date_autopay = utils.months_from_date(self.subscription.date_start, 1)
        calculate_users_in_all_domains(invoice_date_autopay)
        tasks.generate_invoices_based_on_date(invoice_date_autopay)

        autopay_invoice = self.subscription.invoice_set.last()
        self.assertTrue(autopay_invoice.balance <= SMALL_INVOICE_THRESHOLD)
        self.assertIsNotNone(autopay_invoice.date_due)


class TestContractedInvoices(BaseInvoiceTestCase):

    def setUp(self):
        super(TestContractedInvoices, self).setUp()
        self.subscription.service_type = SubscriptionType.IMPLEMENTATION
        self.subscription.save()

        self.invoice_date = utils.months_from_date(
            self.subscription.date_start,
            random.randint(2, self.subscription_length)
        )

    @override_settings(ACCOUNTS_EMAIL='accounts@example.com')
    def test_contracted_invoice_email_recipient(self):
        """
        For contracted invoices, emails should be sent to finance@dimagi.com
        """

        expected_recipient = ["accounts@example.com"]

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        self.assertEqual(Invoice.objects.count(), 1)
        actual_recipient = Invoice.objects.first().email_recipients
        self.assertEqual(actual_recipient, expected_recipient)

    def test_contracted_invoice_email_template(self):
        """
        Emails for contracted invoices should use the contracted invoices template
        """
        expected_template = BillingRecord.INVOICE_CONTRACTED_HTML_TEMPLATE

        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)

        self.assertEqual(BillingRecord.objects.count(), 1)
        actual_template = BillingRecord.objects.first().html_template

        self.assertTrue(actual_template, expected_template)


class TestProductLineItem(BaseInvoiceTestCase):
    """
    Tests that the Product line item is properly generated and prorated (when applicable) in an invoice.
    """

    def setUp(self):
        super(TestProductLineItem, self).setUp()
        self.product_rate = self.subscription.plan_version.product_rate

    def test_standard(self):
        """
        For the Product Line Item, make sure that the Product rate is not prorated:
        - base_cost uses the correct monthly fee
        - base_description is not None
        - unit_description is None
        - unit_cost is 0.0
        - quantity is 1
        - subtotal = monthly fee
        """
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        invoice = self.subscription.invoice_set.latest('date_created')

        product_line_items = invoice.lineitem_set.filter(feature_rate__exact=None)
        self.assertEqual(product_line_items.count(), 1)

        product_line_item = product_line_items.get()
        self.assertIsNotNone(product_line_item.base_description)
        self.assertEqual(product_line_item.base_cost, self.product_rate.monthly_fee)

        self.assertIsNone(product_line_item.unit_description)
        self.assertEqual(product_line_item.unit_cost, Decimal('0.0000'))
        self.assertEqual(product_line_item.quantity, 1)

        self.assertEqual(product_line_item.subtotal, self.product_rate.monthly_fee)

        # no adjustments
        self.assertEqual(product_line_item.total, self.product_rate.monthly_fee)

    def test_prorate(self):
        """
        Make sure that the product is prorated for the first and last invoices, which fall in a partial month:
        - base_cost is 0.0
        - base_description is None
        - unit_description is not None
        - unit_cost is prorated
        - quantity > 1
        - subtotal = unit_cost * quantity
        """
        first_invoice_date = utils.months_from_date(self.subscription.date_start, 1)
        tasks.generate_invoices_based_on_date(first_invoice_date)
        last_invoice_date = utils.months_from_date(self.subscription.date_end, 1)
        tasks.generate_invoices_based_on_date(last_invoice_date)

        for invoice in self.subscription.invoice_set.all():
            product_line_items = invoice.lineitem_set.filter(feature_rate__exact=None)
            self.assertEqual(product_line_items.count(), 1)

            product_line_item = product_line_items.get()

            days_prorated_by_invoice_start_date = {
                datetime.date(2016, 2, 23): 7,
                datetime.date(2017, 5, 1): 22,
            }
            days_in_month_by_invoice_start_date = {
                datetime.date(2016, 2, 23): 29,
                datetime.date(2017, 5, 1): 31,
            }

            self.assertEqual(product_line_item.quantity, days_prorated_by_invoice_start_date[invoice.date_start])
            self.assertEqual(
                product_line_item.unit_cost,
                Decimal("%.2f" % round(
                    self.product_rate.monthly_fee / days_in_month_by_invoice_start_date[invoice.date_start], 2
                ))
            )
            self.assertIsNotNone(product_line_item.unit_description)

            self.assertEqual(product_line_item.base_cost, Decimal('0.0000'))
            self.assertIsNone(product_line_item.base_description)

            self.assertEqual(product_line_item.subtotal, product_line_item.unit_cost * product_line_item.quantity)

            # no adjustments
            self.assertEqual(product_line_item.total, product_line_item.unit_cost * product_line_item.quantity)


class TestUserLineItem(BaseInvoiceTestCase):

    is_using_test_plans = True

    def setUp(self):
        super(TestUserLineItem, self).setUp()
        self.user_rate = self.subscription.plan_version.feature_rates.filter(
            feature__feature_type=FeatureType.USER)[:1].get()

    def test_under_limit(self):
        """
        Make sure that the User rate produced:
        - base_description is None
        - base_cost is 0.0
        - unit_cost is equal to the per_excess_fee
        - quantity is equal to 0
        - unit_description is None
        - total and subtotals are 0.0
        """
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))

        def num_users():
            return random.randint(0, self.user_rate.monthly_limit)
        num_active = num_users()
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_active)

        num_inactive = num_users()
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_inactive, is_active=False)

        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        invoice = self.subscription.invoice_set.latest('date_created')
        user_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.USER).get()

        self.assertIsNone(user_line_item.base_description)
        self.assertEqual(user_line_item.base_cost, Decimal('0.0000'))
        self.assertIsNone(user_line_item.unit_description)
        self.assertEqual(user_line_item.quantity, 0)
        self.assertEqual(user_line_item.unit_cost, self.user_rate.per_excess_fee)
        self.assertEqual(user_line_item.subtotal, Decimal('0.0000'))
        self.assertEqual(user_line_item.total, Decimal('0.0000'))

    def test_over_limit(self):
        """
        Make sure that the User rate produced:
        - base_description is None
        - base_cost is 0.0
        - unit_description is not None
        - unit_cost is equal to the per_excess_fee on the user rate
        - quantity is equal to number of commcare users in that domain minus the monthly_limit on the user rate
        - total and subtotals are equal to number of extra users * per_excess_fee
        """
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))

        def num_users():
            return random.randint(self.user_rate.monthly_limit + 1, self.user_rate.monthly_limit + 2)
        num_active = num_users()
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_active)

        num_inactive = num_users()
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_inactive, is_active=False)

        calculate_users_in_all_domains(datetime.date(invoice_date.year, invoice_date.month, 1))
        tasks.generate_invoices_based_on_date(invoice_date)
        invoice = self.subscription.invoice_set.latest('date_created')
        user_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.USER).get()

        # there is no base cost
        self.assertIsNone(user_line_item.base_description)
        self.assertEqual(user_line_item.base_cost, Decimal('0.0000'))

        num_to_charge = num_active - self.user_rate.monthly_limit
        self.assertIsNotNone(user_line_item.unit_description)
        self.assertEqual(user_line_item.quantity, num_to_charge)
        self.assertEqual(user_line_item.unit_cost, self.user_rate.per_excess_fee)
        self.assertEqual(user_line_item.subtotal, num_to_charge * self.user_rate.per_excess_fee)
        self.assertEqual(user_line_item.total, num_to_charge * self.user_rate.per_excess_fee)

    def test_community_over_limit(self):
        """
        For a domain under community (no subscription) with users over the community limit, make sure that:
        - base_description is None
        - base_cost is 0.0
        - unit_description is not None
        - unit_cost is equal to the per_excess_fee on the user rate
        - quantity is equal to number of commcare users in that domain minus the monthly_limit on the user rate
        - total and subtotals are equal to number of extra users * per_excess_fee
        """
        domain = generator.arbitrary_domain()
        self.addCleanup(domain.delete)
        num_active = generator.create_excess_community_users(domain)

        account = BillingAccount.get_or_create_account_by_domain(
            domain, created_by=self.dimagi_user)[0]
        generator.arbitrary_contact_info(account, self.dimagi_user)
        today = datetime.date.today()
        account.date_confirmed_extra_charges = today
        account.save()

        calculate_users_in_all_domains(datetime.date(today.year, today.month, 1))
        tasks.generate_invoices_based_on_date(datetime.date.today())
        subscriber = Subscriber.objects.get(domain=domain.name)
        invoice = Invoice.objects.filter(subscription__subscriber=subscriber).get()
        user_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.USER).get()

        self.assertIsNone(user_line_item.base_description)
        self.assertEqual(user_line_item.base_cost, Decimal('0.0000'))

        community_plan = DefaultProductPlan.get_default_plan_version()
        num_to_charge = num_active - community_plan.user_limit
        self.assertIsNotNone(user_line_item.unit_description)
        self.assertEqual(user_line_item.quantity, num_to_charge)
        self.assertEqual(user_line_item.unit_cost, self.user_rate.per_excess_fee)
        self.assertEqual(user_line_item.subtotal, num_to_charge * self.user_rate.per_excess_fee)
        self.assertEqual(user_line_item.total, num_to_charge * self.user_rate.per_excess_fee)


class TestWebUserLineItem(BaseInvoiceTestCase):

    is_using_test_plans = True
    is_testing_web_user_feature = True

    def setUp(self):
        super(TestWebUserLineItem, self).setUp()
        self.web_user_rate = self.subscription.plan_version.feature_rates.filter(
            feature__feature_type=FeatureType.WEB_USER)[:1].get()
        self.subscription.account.bill_web_user = True
        self.subscription.account.save()

    def test_under_limit(self):
        """
        Make sure that the Web User rate produced:
        - base_description is None
        - base_cost is 0.0
        - unit_cost is equal to the per_excess_fee
        - quantity is equal to 0
        - unit_description is None
        - total and subtotals are 0.0
        """
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))

        def num_users():
            return random.randint(0, self.web_user_rate.monthly_limit)
        num_active = num_users()
        generator.arbitrary_webusers_for_domain(self.domain.name, num_active)

        num_inactive = num_users()
        generator.arbitrary_webusers_for_domain(self.domain.name, num_inactive, is_active=False)

        calculate_users_in_all_domains(invoice_date)
        tasks.calculate_web_users_in_all_billing_accounts(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        invoice = self.subscription.invoice_set.latest('date_created')
        web_user_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.WEB_USER).get()

        self.assertIsNone(web_user_line_item.base_description)
        self.assertEqual(web_user_line_item.base_cost, Decimal('0.0000'))
        self.assertIsNone(web_user_line_item.unit_description)
        self.assertEqual(web_user_line_item.quantity, 0)
        self.assertEqual(web_user_line_item.unit_cost, self.web_user_rate.per_excess_fee)
        self.assertEqual(web_user_line_item.subtotal, Decimal('0.0000'))
        self.assertEqual(web_user_line_item.total, Decimal('0.0000'))

    def test_over_limit(self):
        """
        Make sure that the Web User rate produced:
        - base_description is None
        - base_cost is 0.0
        - unit_description is not None
        - unit_cost is equal to the per_excess_fee on the web user rate
        - quantity is equal to number of web users in that account minus the monthly_limit on the web user rate
        - total and subtotals are equal to number of extra users * per_excess_fee
        """
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))

        def num_users():
            return random.randint(self.web_user_rate.monthly_limit + 1, self.web_user_rate.monthly_limit + 2)
        num_active = num_users()
        generator.arbitrary_webusers_for_domain(self.domain.name, num_active)

        num_inactive = num_users()
        generator.arbitrary_webusers_for_domain(self.domain.name, num_inactive, is_active=False)

        calculate_users_in_all_domains(datetime.date(invoice_date.year, invoice_date.month, 1))
        tasks.calculate_web_users_in_all_billing_accounts(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        invoice = self.subscription.invoice_set.latest('date_created')
        web_user_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.WEB_USER).get()

        # there is no base cost
        self.assertIsNone(web_user_line_item.base_description)
        self.assertEqual(web_user_line_item.base_cost, Decimal('0.0000'))

        num_to_charge = num_active - self.web_user_rate.monthly_limit
        self.assertIsNotNone(web_user_line_item.unit_description)
        self.assertEqual(web_user_line_item.quantity, num_to_charge)
        self.assertEqual(web_user_line_item.unit_cost, self.web_user_rate.per_excess_fee)
        self.assertEqual(web_user_line_item.subtotal, num_to_charge * self.web_user_rate.per_excess_fee)
        self.assertEqual(web_user_line_item.total, num_to_charge * self.web_user_rate.per_excess_fee)

    def test_no_line_item_when_bill_web_user_flag_is_false(self):
        """
        For a billing account that have bill_web_user flag set to False
        - there should be no web user line item on the invoice
        """
        self.subscription.account.bill_web_user = False
        self.subscription.account.save()

        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))

        def num_users():
            return random.randint(self.web_user_rate.monthly_limit + 1, self.web_user_rate.monthly_limit + 2)
        num_active = num_users()
        generator.arbitrary_webusers_for_domain(self.domain.name, num_active)

        num_inactive = num_users()
        generator.arbitrary_webusers_for_domain(self.domain.name, num_inactive, is_active=False)

        calculate_users_in_all_domains(datetime.date(invoice_date.year, invoice_date.month, 1))
        tasks.calculate_web_users_in_all_billing_accounts(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)
        invoice = self.subscription.invoice_set.latest('date_created')
        self.assertEqual(invoice.lineitem_set.get_feature_by_type(FeatureType.WEB_USER).count(), 0)


class TestSmsLineItem(BaseInvoiceTestCase):
    is_using_test_plans = True

    @classmethod
    def setUpClass(cls):
        super(TestSmsLineItem, cls).setUpClass()
        cls.sms_rate = cls.subscription.plan_version.feature_rates.filter(
            feature__feature_type=FeatureType.SMS
        ).get()
        cls.invoice_date = utils.months_from_date(
            cls.subscription.date_start, random.randint(2, cls.subscription_length)
        )
        cls.sms_date = utils.months_from_date(cls.invoice_date, -1)

    @classmethod
    def tearDownClass(cls):
        cls._delete_sms_billables()
        super(TestSmsLineItem, cls).tearDownClass()

    def test_under_limit(self):
        """
        Make sure that the Line Item for the SMS Rate has the following:
        - base_description is None
        - base_cost is 0.0
        - unit_description is not None
        - unit_cost is 0.0
        - quantity is equal to 1
        - total and subtotals are 0.0
        """
        num_sms = random.randint(0, self.sms_rate.monthly_limit // 2)
        arbitrary_sms_billables_for_domain(
            self.subscription.subscriber.domain, self.sms_date, num_sms, direction=INCOMING
        )
        arbitrary_sms_billables_for_domain(
            self.subscription.subscriber.domain, self.sms_date, num_sms, direction=OUTGOING
        )
        sms_line_item = self._create_sms_line_item()

        # there is no base cost
        self.assertIsNone(sms_line_item.base_description)
        self.assertEqual(sms_line_item.base_cost, Decimal('0.0000'))

        self.assertEqual(sms_line_item.quantity, 1)
        self.assertEqual(sms_line_item.unit_cost, Decimal('0.0000'))
        self.assertIsNotNone(sms_line_item.unit_description)
        self.assertEqual(sms_line_item.subtotal, Decimal('0.0000'))
        self.assertEqual(sms_line_item.total, Decimal('0.0000'))

    def test_over_limit(self):
        """
        Make sure that the Line Item for the SMS Rate has the following:
        - base_description is None
        - base_cost is 0.0
        - unit_description is not None
        - unit_cost is greater than 0.0
        - quantity is equal to 1
        - total and subtotals are greater than zero
        """
        num_sms = random.randint(self.sms_rate.monthly_limit + 1, self.sms_rate.monthly_limit + 2)
        billables = arbitrary_sms_billables_for_domain(
            self.subscription.subscriber.domain, self.sms_date, num_sms
        )
        sms_line_item = self._create_sms_line_item()

        # there is no base cost
        self.assertIsNone(sms_line_item.base_description)
        self.assertEqual(sms_line_item.base_cost, Decimal('0.0000'))

        sms_cost = sum(
            billable.gateway_charge + billable.usage_charge
            for billable in billables[self.sms_rate.monthly_limit:]
        )

        self.assertEqual(sms_line_item.quantity, 1)
        self.assertEqual(sms_line_item.unit_cost, sms_cost)
        self.assertIsNotNone(sms_line_item.unit_description)

        self.assertEqual(sms_line_item.subtotal, sms_cost)
        self.assertEqual(sms_line_item.total, sms_cost)

    def test_multipart_under_limit(self):
        self._create_multipart_billables(self.sms_rate.monthly_limit)

        sms_line_item = self._create_sms_line_item()

        self.assertIsNone(sms_line_item.base_description)
        self.assertEqual(sms_line_item.base_cost, Decimal('0.0000'))

        self.assertEqual(sms_line_item.quantity, 1)
        self.assertEqual(sms_line_item.unit_cost, Decimal('0.0000'))
        self.assertIsNotNone(sms_line_item.unit_description)
        self.assertEqual(sms_line_item.subtotal, Decimal('0.0000'))
        self.assertEqual(sms_line_item.total, Decimal('0.0000'))

    def test_multipart_over_limit_and_part_of_the_billable_is_under_limit(self):
        """
        In this test, we particularly test the scenario that
        half of the billable is within the limit, the remaining half exceeds the limit.
        So it's crucial to use test plan in this test instead of default plan whose limit is 0.
        """

        def _set_billable_date_sent_day(sms_billable, day):
            sms_billable.date_sent = datetime.date(
                sms_billable.date_sent.year,
                sms_billable.date_sent.month,
                day
            )
            sms_billable.save()

        self._create_multipart_billables(self.sms_rate.monthly_limit - 1)
        for billable in SmsBillable.objects.all():
            _set_billable_date_sent_day(billable, 1)

        half_charged_billable = arbitrary_sms_billables_for_domain(
            self.subscription.subscriber.domain, self.sms_date, 1, multipart_count=2
        )[0]
        _set_billable_date_sent_day(half_charged_billable, 2)

        fully_charged_billable = arbitrary_sms_billables_for_domain(
            self.subscription.subscriber.domain, self.sms_date, 1, multipart_count=random.randint(2, 5)
        )[0]
        _set_billable_date_sent_day(fully_charged_billable, 3)

        sms_cost = (
            (half_charged_billable.gateway_charge + half_charged_billable.usage_charge) / 2
            + fully_charged_billable.gateway_charge + fully_charged_billable.usage_charge
        )

        sms_line_item = self._create_sms_line_item()

        self.assertEqual(sms_line_item.quantity, 1)
        self.assertEqual(sms_line_item.unit_cost, sms_cost)
        self.assertIsNotNone(sms_line_item.unit_description)

        self.assertEqual(sms_line_item.subtotal, sms_cost)
        self.assertEqual(sms_line_item.total, sms_cost)

    def _create_sms_line_item(self):
        calculate_users_in_all_domains(self.invoice_date)
        tasks.generate_invoices_based_on_date(self.invoice_date)
        invoice = self.subscription.invoice_set.latest('date_created')
        return invoice.lineitem_set.get_feature_by_type(FeatureType.SMS).get()

    def _create_multipart_billables(self, total_parts):
        count_parts = 0
        while True:
            multipart_count = random.randint(1, 5)
            if count_parts + multipart_count <= total_parts:
                arbitrary_sms_billables_for_domain(
                    self.subscription.subscriber.domain, self.sms_date, 1, multipart_count=multipart_count
                )
                count_parts += multipart_count
            else:
                break
        remaining_parts = total_parts - count_parts
        if remaining_parts > 0:
            arbitrary_sms_billables_for_domain(
                self.subscription.subscriber.domain, self.sms_date, 1, multipart_count=remaining_parts
            )

    @classmethod
    def _delete_sms_billables(cls):
        SmsBillable.objects.all().delete()
        SmsGatewayFee.objects.all().delete()
        SmsGatewayFeeCriteria.objects.all().delete()
        SmsUsageFee.objects.all().delete()
        SmsUsageFeeCriteria.objects.all().delete()


class TestInvoiceRecipients(BaseInvoiceTestCase):

    def test_implementation_subscription_with_dimagi_contact(self):
        self._setup_implementation_subscription_with_dimagi_contact()

        invoice_date = utils.months_from_date(self.subscription.date_start, 1)
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertListEqual(sent_email.to, ['dimagi_contact@test.com'])
        self.assertListEqual(sent_email.cc, [settings.ACCOUNTS_EMAIL])

    def test_implementation_subscription_without_dimagi_contact(self):
        self._setup_implementation_subscription_without_dimagi_contact()

        invoice_date = utils.months_from_date(self.subscription.date_start, 1)
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertListEqual(sent_email.to, [settings.ACCOUNTS_EMAIL])
        self.assertListEqual(sent_email.cc, [])

    def test_product_subscription(self):
        self._setup_product_subscription()

        invoice_date = utils.months_from_date(self.subscription.date_start, 1)
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(len(mail.outbox), 2)
        self.assertListEqual(mail.outbox[0].to, ['client1@test.com'])
        self.assertListEqual(mail.outbox[0].cc, [])
        self.assertListEqual(mail.outbox[1].to, ['client2@test.com'])
        self.assertListEqual(mail.outbox[1].cc, [])

    def test_specified_recipients_implementation_with_dimagi_contact(self):
        self._setup_implementation_subscription_with_dimagi_contact()
        self._test_specified_recipients()

    def test_specified_recipients_implementation_without_dimagi_contact(self):
        self._setup_implementation_subscription_without_dimagi_contact()
        self._test_specified_recipients()

    def test_specified_recipients_product(self):
        self._setup_product_subscription()
        self._test_specified_recipients()

    def test_unspecified_recipients_product(self):
        self._setup_product_subscription_with_admin_user()

        invoice_date = utils.months_from_date(self.subscription.date_start, 1)
        calculate_users_in_all_domains(invoice_date)
        tasks.generate_invoices_based_on_date(invoice_date)

        self.assertEqual(len(mail.outbox), 1)
        self.assertListEqual(mail.outbox[0].to, ['adminwebuser@test.com'])
        self.assertListEqual(mail.outbox[0].cc, [])

    def _setup_implementation_subscription_with_dimagi_contact(self):
        self.subscription.service_type = SubscriptionType.IMPLEMENTATION
        self.subscription.plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.PRO)
        self.subscription.save()
        self.subscription.account.dimagi_contact = 'dimagi_contact@test.com'
        self.subscription.account.save()

    def _setup_implementation_subscription_without_dimagi_contact(self):
        self.subscription.service_type = SubscriptionType.IMPLEMENTATION
        self.subscription.plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.PRO)
        self.subscription.save()
        self.subscription.account.dimagi_contact = ''
        self.subscription.account.save()

    def _setup_product_subscription(self):
        self.subscription.service_type = SubscriptionType.PRODUCT
        self.subscription.save()
        self.subscription.account.billingcontactinfo.email_list = ['client1@test.com', 'client2@test.com']
        self.subscription.account.billingcontactinfo.save()

    def _setup_product_subscription_with_admin_user(self):
        self.subscription.service_type = SubscriptionType.PRODUCT
        self.subscription.save()
        self.subscription.account.billingcontactinfo.email_list = []
        self.subscription.account.billingcontactinfo.save()
        web_user = WebUser.create(
            domain=self.domain.name,
            username=generator.create_arbitrary_web_user_name(),
            password='123',
            created_by=None,
            created_via=None,
            email="adminwebuser@test.com",
        )
        web_user.set_role(self.domain.name, "admin")
        web_user.save()

    def _test_specified_recipients(self):
        calculate_users_in_all_domains(
            datetime.date(self.subscription.date_start.year, self.subscription.date_start.month + 1, 1))
        DomainInvoiceFactory(
            self.subscription.date_start,
            utils.months_from_date(self.subscription.date_start, 1) - datetime.timedelta(days=1),
            self.subscription.subscriber.domain,
            recipients=['recipient1@test.com', 'recipient2@test.com']
        ).create_invoices()

        self.assertEqual(len(mail.outbox), 2)
        self.assertListEqual(mail.outbox[0].to, ['recipient1@test.com'])
        self.assertListEqual(mail.outbox[0].cc, [])
        self.assertListEqual(mail.outbox[1].to, ['recipient2@test.com'])
        self.assertListEqual(mail.outbox[1].cc, [])
