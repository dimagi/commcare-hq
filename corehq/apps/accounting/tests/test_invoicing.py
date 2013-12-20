from decimal import Decimal
import random
from django.test import TestCase

from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import (SmsGatewayFee, SmsGatewayFeeCriteria, SmsUsageFee, SmsUsageFeeCriteria,
                                             SmsBillable)
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.apps.accounting import generator, tasks, utils
from corehq.apps.accounting.models import Invoice, FeatureType, LineItem


class BaseInvoiceTestCase(TestCase):

    def setUp(self):
        self.billing_contact = generator.arbitrary_web_user()
        self.dimagi_user = generator.arbitrary_web_user(is_dimagi=True)
        self.currency = generator.init_default_currency()
        self.account = generator.billing_account(self.dimagi_user, self.billing_contact)
        self.domain = generator.arbitrary_domain()

        generator.instantiate_subscribable_plans()
        generator.instantiate_community_plans()
        self.subscription, self.subscription_length = generator.generate_domain_subscription_from_date(
            generator.get_start_date(), self.account, self.domain.name, num_months=3,
        )

    def tearDown(self):
        self.billing_contact.delete()
        self.dimagi_user.delete()
        self.domain.delete()

        LineItem.objects.all().delete()
        Invoice.objects.all().delete()
        generator.delete_all_subscriptions()
        generator.delete_all_plans()
        generator.delete_all_accounts()


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

        invoice = self.subscription.invoice_set.latest('date_created')

        num_product_line_items = invoice.lineitem_set.get_products().count()
        self.assertEqual(num_product_line_items, self.subscription.plan.product_rates.count())

        num_feature_line_items = invoice.lineitem_set.get_features().count()
        self.assertEqual(num_feature_line_items, self.subscription.plan.feature_rates.count())
        self.assertEqual(invoice.subscription, self.subscription)
        self.assertGreater(invoice.balance, Decimal('0.0'))

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
        pass
        # todo


class TestProductLineItem(BaseInvoiceTestCase):
    """
    Tests that the Product line item is properly generated and prorated (when applicable) in an invoice.
    """

    def setUp(self):
        super(TestProductLineItem, self).setUp()
        self.product_rate = self.subscription.plan.product_rates.all()[0]
        self.prorate = Decimal("%.2f" % round(self.product_rate.monthly_fee / 30, 2))

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

        product_line_item = product_line_items[:1].get()
        self.assertIsNotNone(product_line_item.base_description)
        self.assertEqual(product_line_item.base_cost, self.product_rate.monthly_fee)

        self.assertIsNone(product_line_item.unit_description)
        self.assertEqual(product_line_item.unit_cost, Decimal('0.0'))
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

            product_line_item = invoice.lineitem_set.filter(feature_rate__exact=None)[:1].get()

            self.assertGreater(product_line_item.quantity, 1)
            self.assertEqual(product_line_item.unit_cost, self.prorate)
            self.assertIsNotNone(product_line_item.unit_description)

            self.assertEqual(product_line_item.base_cost, Decimal('0.0'))
            self.assertIsNone(product_line_item.base_description)

            self.assertEqual(product_line_item.subtotal, product_line_item.unit_cost * product_line_item.quantity)

            # no adjustments
            self.assertEqual(product_line_item.total, product_line_item.unit_cost * product_line_item.quantity)

    def test_community(self):
        """
        For Community plans (plan monthly fee is 0.0) that incur other rate charges, like users or SMS messages,
        make sure that the following is true:
        - base_description is None
        - unit_description is None
        - unit_cost is equal to per excess fee
        - quantity is equal to 0
        - total and subtotals are 0.0
        """
        # todo
        pass


class TestUserLineItem(BaseInvoiceTestCase):

    def setUp(self):
        super(TestUserLineItem, self).setUp()
        self.user_rate = self.subscription.plan.feature_rates.filter(feature__feature_type=FeatureType.USER)[:1].get()

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

        num_users = lambda: random.randint(0, self.user_rate.monthly_limit / 2)
        num_active = num_users()
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_active)

        num_inactive = num_users()
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_inactive, is_active=False)

        tasks.generate_invoices(invoice_date)
        invoice = self.subscription.invoice_set.latest('date_created')
        user_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.USER)[:1].get()

        self.assertIsNone(user_line_item.base_description)
        self.assertEqual(user_line_item.base_cost, Decimal('0.0'))
        self.assertIsNone(user_line_item.unit_description)
        self.assertEqual(user_line_item.quantity, 0)
        self.assertEqual(user_line_item.unit_cost, self.user_rate.per_excess_fee)
        self.assertEqual(user_line_item.subtotal, Decimal('0.0'))
        self.assertEqual(user_line_item.total, Decimal('0.0'))

        self._delete_users()

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
        user_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.USER)[:1].get()

        # there is no base cost
        self.assertIsNone(user_line_item.base_description)
        self.assertEqual(user_line_item.base_cost, Decimal('0.0'))

        num_to_charge = (num_active + num_inactive) - self.user_rate.monthly_limit
        self.assertIsNotNone(user_line_item.unit_description)
        self.assertEqual(user_line_item.quantity, num_to_charge)
        self.assertEqual(user_line_item.unit_cost, self.user_rate.per_excess_fee)
        self.assertEqual(user_line_item.subtotal, num_to_charge * self.user_rate.per_excess_fee)
        self.assertEqual(user_line_item.total, num_to_charge * self.user_rate.per_excess_fee)

        self._delete_users()

    def test_community_charges_over_limit(self):
        """
        For a domain under community (no subscription) with users over the community limit, make sure that:
        - base_description is None
        - base_cost is 0.0
        - unit_description is not None
        - unit_cost is equal to the per_excess_fee on the user rate
        - quantity is equal to number of commcare users in that domain minus the monthly_limit on the user rate
        - total and subtotals are equal to number of extra users * per_excess_fee
        """
        pass
        # todo

    def _delete_users(self):
        for user in WebUser.by_domain(self.domain.name):
            user.delete()
        for user in CommCareUser.by_domain(self.domain.name):
            user.delete()
        for user in CommCareUser.by_domain(self.domain.name, is_active=False):
            user.delete()


class TestSmsLineItem(BaseInvoiceTestCase):

    def setUp(self):
        super(TestSmsLineItem, self).setUp()
        self.sms_rate = self.subscription.plan.feature_rates.filter(feature__feature_type=FeatureType.SMS)[:1].get()

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
        invoice_date = utils.months_from_date(self.subscription.date_start, random.randint(2, self.subscription_length))
        sms_date = utils.months_from_date(invoice_date, -1)

        num_sms = random.randint(0, self.sms_rate.monthly_limit/2)
        generator.arbitrary_sms_billables_for_domain(
            self.subscription.subscriber.domain, INCOMING, sms_date, num_sms
        )
        generator.arbitrary_sms_billables_for_domain(
            self.subscription.subscriber.domain, OUTGOING, sms_date, num_sms
        )

        tasks.generate_invoices(invoice_date)
        invoice = self.subscription.invoice_set.latest('date_created')
        sms_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.SMS)[:1].get()

        # there is no base cost
        self.assertIsNone(sms_line_item.base_description)
        self.assertEqual(sms_line_item.base_cost, Decimal('0.0'))

        self.assertEqual(sms_line_item.quantity, 1)
        self.assertEqual(sms_line_item.unit_cost, Decimal('0.0'))
        self.assertIsNotNone(sms_line_item.unit_description)
        self.assertEqual(sms_line_item.subtotal, Decimal('0.0'))
        self.assertEqual(sms_line_item.total, Decimal('0.0'))

        self._delete_sms_billables()

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
        invoice_date = utils.months_from_date(self.subscription.date_start, random.randint(2, self.subscription_length))
        sms_date = utils.months_from_date(invoice_date, -1)

        num_sms = random.randint(self.sms_rate.monthly_limit + 1, self.sms_rate.monthly_limit + 2)
        generator.arbitrary_sms_billables_for_domain(
            self.subscription.subscriber.domain, INCOMING, sms_date, num_sms
        )
        generator.arbitrary_sms_billables_for_domain(
            self.subscription.subscriber.domain, OUTGOING, sms_date, num_sms
        )

        tasks.generate_invoices(invoice_date)
        invoice = self.subscription.invoice_set.latest('date_created')
        sms_line_item = invoice.lineitem_set.get_feature_by_type(FeatureType.SMS)[:1].get()

        # there is no base cost
        self.assertIsNone(sms_line_item.base_description)
        self.assertEqual(sms_line_item.base_cost, Decimal('0.0'))

        self.assertEqual(sms_line_item.quantity, 1)
        self.assertGreater(sms_line_item.unit_cost, Decimal('0.0'))
        self.assertIsNotNone(sms_line_item.unit_description)

        self.assertGreater(sms_line_item.subtotal, Decimal('0.0'))
        self.assertGreater(sms_line_item.total, Decimal('0.0'))

        self._delete_sms_billables()

    def test_community_over_limit(self):
        """
        For a domain under community (no subscription) with SMS over the community limit, make sure that:
        - base_description is None
        - base_cost is 0.0
        - unit_description is not None
        - unit_cost is greater than 0.0
        - quantity is equal to 1
        - total and subtotals are greater than zero
        """
        pass

    def _delete_sms_billables(self):
        SmsBillable.objects.all().delete()
        SmsGatewayFee.objects.all().delete()
        SmsGatewayFeeCriteria.objects.all().delete()
        SmsUsageFee.objects.all().delete()
        SmsUsageFeeCriteria.objects.all().delete()
