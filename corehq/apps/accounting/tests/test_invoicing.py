from decimal import Decimal
import random
import datetime

from dimagi.utils.dates import add_months_to_date

from corehq.apps.accounting import tasks, utils
from corehq.apps.accounting.models import (
    SMALL_INVOICE_THRESHOLD,
    BillingAccount,
    BillingRecord,
    CreditAdjustment,
    CreditLine,
    DefaultProductPlan,
    FeatureType,
    Invoice,
    LineItem,
    SoftwarePlanEdition,
    Subscriber,
    Subscription,
    SubscriptionAdjustment,
    SubscriptionType,
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


class BaseInvoiceTestCase(BaseAccountingTest):
    min_subscription_length = 3

    def setUp(self):
        super(BaseInvoiceTestCase, self).setUp()
        self.billing_contact = generator.arbitrary_web_user()
        self.dimagi_user = generator.arbitrary_web_user(is_dimagi=True)
        self.currency = generator.init_default_currency()
        self.account = generator.billing_account(
            self.dimagi_user, self.billing_contact)
        self.domain = generator.arbitrary_domain()

        self.subscription_length = 15  # months
        subscription_start_date = datetime.date(2016, 2, 23)
        subscription_end_date = add_months_to_date(subscription_start_date, self.subscription_length)
        self.subscription = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
        )

        self.community_plan = DefaultProductPlan.get_default_plan_version()

    def tearDown(self):
        CreditAdjustment.objects.all().delete()
        CreditLine.objects.all().delete()

        BillingRecord.objects.all().delete()
        LineItem.objects.all().delete()
        SubscriptionAdjustment.objects.all().delete()
        Invoice.objects.all().delete()
        generator.delete_all_subscriptions()
        generator.delete_all_accounts()

        self.billing_contact.delete()
        self.dimagi_user.delete()
        self.domain.delete()

        super(BaseInvoiceTestCase, self).tearDown()


class TestInvoice(BaseInvoiceTestCase):
    """
    Tests that invoices are properly generated for the first month, last month, and a random month in the middle
    of a subscription for a domain.
    """

    def test_no_invoice_before_start(self):
        """
        No invoice gets created if the subscription didn't start in the previous month.
        """
        tasks.generate_invoices(self.subscription.date_start)
        self.assertEqual(self.subscription.invoice_set.count(), 0)

    def test_subscription_invoice(self):
        invoice_date = utils.months_from_date(self.subscription.date_start, random.randint(2, self.subscription_length))
        tasks.generate_invoices(invoice_date)
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
        tasks.generate_invoices(invoice_date)
        self.assertEqual(self.subscription.invoice_set.count(), 0)

    def test_community_no_charges_no_invoice(self):
        """
        No invoices should be generated for domains that are not on a subscription and do not
        have any per_excess charges on users or SMS messages
        """
        domain = generator.arbitrary_domain()
        tasks.generate_invoices()
        self.assertRaises(Invoice.DoesNotExist,
                          lambda: Invoice.objects.get(subscription__subscriber__domain=domain.name))
        domain.delete()

    def test_community_invoice(self):
        """
        For an unsubscribed domain with any charges over the community limit for the month of invoicing,
        make sure that an invoice is generated in addition to a subscription for that month to
        the community plan.
        """
        domain = generator.arbitrary_domain()
        generator.create_excess_community_users(domain)
        account = BillingAccount.get_or_create_account_by_domain(
            domain, created_by=self.dimagi_user)[0]
        billing_contact = generator.arbitrary_contact_info(account, self.dimagi_user)
        billing_contact.save()
        account.date_confirmed_extra_charges = datetime.date.today()
        account.save()
        tasks.generate_invoices()
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
        domain.delete()

    def test_date_due_not_set_small_invoice(self):
        """Date Due doesn't get set if the invoice is small"""
        Subscription.objects.all().delete()
        plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.STANDARD)

        subscription_length = 5  # months
        subscription_start_date = datetime.date(2016, 2, 23)
        subscription_end_date = add_months_to_date(subscription_start_date, subscription_length)
        subscription = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
            plan_version=plan_version,
        )

        invoice_date_small = utils.months_from_date(subscription.date_start, 1)
        tasks.generate_invoices(invoice_date_small)
        small_invoice = subscription.invoice_set.first()

        self.assertTrue(small_invoice.balance <= SMALL_INVOICE_THRESHOLD)
        self.assertIsNone(small_invoice.date_due)

    def test_date_due_set_large_invoice(self):
        """Date Due only gets set for a large invoice (> $100)"""
        Subscription.objects.all().delete()
        plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.ADVANCED)

        subscription_length = 5  # months
        subscription_start_date = datetime.date(2016, 2, 23)
        subscription_end_date = add_months_to_date(subscription_start_date, subscription_length)
        subscription = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
            plan_version=plan_version
        )

        invoice_date_large = utils.months_from_date(subscription.date_start, 3)
        tasks.generate_invoices(invoice_date_large)
        large_invoice = subscription.invoice_set.last()

        self.assertTrue(large_invoice.balance > SMALL_INVOICE_THRESHOLD)
        self.assertIsNotNone(large_invoice.date_due)

    def test_date_due_gets_set_autopay(self):
        """Date due always gets set for autopay """
        Subscription.objects.all().delete()
        plan_version = DefaultProductPlan.get_default_plan_version(SoftwarePlanEdition.STANDARD)

        subscription_length = 4
        subscription_start_date = datetime.date(2016, 2, 23)
        subscription_end_date = add_months_to_date(subscription_start_date, subscription_length)
        autopay_subscription = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
            plan_version=plan_version
        )

        autopay_subscription.account.update_autopay_user(self.billing_contact.username, self.domain)
        invoice_date_autopay = utils.months_from_date(autopay_subscription.date_start, 1)
        tasks.generate_invoices(invoice_date_autopay)

        autopay_invoice = autopay_subscription.invoice_set.last()
        self.assertTrue(autopay_invoice.balance <= SMALL_INVOICE_THRESHOLD)
        self.assertIsNotNone(autopay_invoice.date_due)


class TestContractedInvoices(BaseInvoiceTestCase):

    def setUp(self):
        super(TestContractedInvoices, self).setUp()
        generator.delete_all_subscriptions()

        self.subscription_length = self.min_subscription_length
        subscription_start_date = datetime.date(2016, 2, 23)
        subscription_end_date = add_months_to_date(subscription_start_date, self.subscription_length)
        self.subscription = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=subscription_start_date,
            date_end=subscription_end_date,
            service_type=SubscriptionType.IMPLEMENTATION,
        )

        self.invoice_date = utils.months_from_date(
            self.subscription.date_start,
            random.randint(2, self.subscription_length)
        )

    def test_contracted_invoice_email_recipient(self):
        """
        For contracted invoices, emails should be sent to finance@dimagi.com
        """

        expected_recipient = ["accounts@dimagi.com"]

        tasks.generate_invoices(self.invoice_date)

        self.assertEqual(Invoice.objects.count(), 1)
        actual_recipient = Invoice.objects.first().email_recipients
        self.assertEqual(actual_recipient, expected_recipient)

    def test_contracted_invoice_email_template(self):
        """
        Emails for contracted invoices should use the contracted invoices template
        """
        expected_template = BillingRecord.INVOICE_CONTRACTED_HTML_TEMPLATE

        tasks.generate_invoices(self.invoice_date)

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
        invoice_date = utils.months_from_date(self.subscription.date_start, random.randint(2, self.subscription_length))
        tasks.generate_invoices(invoice_date)
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
        tasks.generate_invoices(first_invoice_date)
        last_invoice_date = utils.months_from_date(self.subscription.date_end, 1)
        tasks.generate_invoices(last_invoice_date)

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

    def setUp(self):
        super(TestUserLineItem, self).setUp()
        self.user_rate = self.subscription.plan_version.feature_rates.filter(feature__feature_type=FeatureType.USER)[:1].get()

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
        invoice_date = utils.months_from_date(self.subscription.date_start, random.randint(2, self.subscription_length))

        num_users = lambda: random.randint(0, self.user_rate.monthly_limit)
        num_active = num_users()
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_active)

        num_inactive = num_users()
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_inactive, is_active=False)

        tasks.generate_invoices(invoice_date)
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
        invoice_date = utils.months_from_date(self.subscription.date_start, random.randint(2, self.subscription_length))

        num_users = lambda: random.randint(self.user_rate.monthly_limit + 1, self.user_rate.monthly_limit + 2)
        num_active = num_users()
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_active)

        num_inactive = num_users()
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_inactive, is_active=False)

        tasks.generate_invoices(invoice_date)
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
        num_active = generator.create_excess_community_users(domain)

        account = BillingAccount.get_or_create_account_by_domain(
            domain, created_by=self.dimagi_user)[0]
        billing_contact = generator.arbitrary_contact_info(account, self.dimagi_user)
        billing_contact.save()
        account.date_confirmed_extra_charges = datetime.date.today()
        account.save()

        tasks.generate_invoices()
        subscriber = Subscriber.objects.get(domain=domain.name)
        invoice = Invoice.objects.filter(subscription__subscriber=subscriber).get()
        user_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.USER).get()

        self.assertIsNone(user_line_item.base_description)
        self.assertEqual(user_line_item.base_cost, Decimal('0.0000'))

        num_to_charge = num_active - self.community_plan.user_limit
        self.assertIsNotNone(user_line_item.unit_description)
        self.assertEqual(user_line_item.quantity, num_to_charge)
        self.assertEqual(user_line_item.unit_cost, self.user_rate.per_excess_fee)
        self.assertEqual(user_line_item.subtotal, num_to_charge * self.user_rate.per_excess_fee)
        self.assertEqual(user_line_item.total, num_to_charge * self.user_rate.per_excess_fee)
        domain.delete()


class TestSmsLineItem(BaseInvoiceTestCase):

    def setUp(self):
        super(TestSmsLineItem, self).setUp()
        self.sms_rate = self.subscription.plan_version.feature_rates.filter(
            feature__feature_type=FeatureType.SMS
        ).get()
        self.invoice_date = utils.months_from_date(
            self.subscription.date_start, random.randint(2, self.subscription_length)
        )
        self.sms_date = utils.months_from_date(self.invoice_date, -1)

    def tearDown(self):
        self._delete_sms_billables()
        super(TestSmsLineItem, self).tearDown()

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
        num_sms = random.randint(0, self.sms_rate.monthly_limit/2)
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

    def test_multipart_over_limit(self):
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
        tasks.generate_invoices(self.invoice_date)
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

    def _delete_sms_billables(self):
        SmsBillable.objects.all().delete()
        SmsGatewayFee.objects.all().delete()
        SmsGatewayFeeCriteria.objects.all().delete()
        SmsUsageFee.objects.all().delete()
        SmsUsageFeeCriteria.objects.all().delete()
