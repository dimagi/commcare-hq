import datetime
import random
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from corehq.apps.accounting import tasks, utils
from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    DomainUserHistory,
    Feature,
    FeatureRate,
    FeatureType,
    FormSubmittingMobileWorkerHistory,
    Invoice,
    Subscriber,
    Subscription,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
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
        self.create_invoices(invoice_date)
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
        last_invoice_date = utils.months_from_date(self.subscription.date_end, 1)
        self.create_invoices(first_invoice_date, calculate_users=False)
        self.create_invoices(last_invoice_date, calculate_users=False)

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

        self.create_invoices(invoice_date)

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

        self.create_invoices(invoice_date)

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
        For a domain under community with users over the community limit, make sure that:
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

        community_plan = DefaultProductPlan.get_default_plan_version()
        Subscription.new_domain_subscription(
            account, domain.name, community_plan,
            date_start=datetime.date(today.year, today.month, 1) - relativedelta(months=1),
        )

        self.create_invoices(datetime.date(today.year, today.month, 1))
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


class TestFormSubmittingMobileWorkerLineItem(BaseInvoiceTestCase):

    def setUp(self):
        super().setUp()
        self.feature_rate = FeatureRate.objects.create(
            feature=Feature.objects.get(name=FeatureType.FORM_SUBMITTING_MOBILE_WORKER),
            monthly_limit=10,
            per_excess_fee=Decimal('3.00')
        )
        plan_feature_rates = generator.default_feature_rates() + [self.feature_rate]
        plan_version = generator.custom_plan_version(feature_rates=plan_feature_rates)

        # delete the old subscription first so our custom plan version doesn't compete with it
        self.subscription.delete()
        self.subscription = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=self.subscription_start_date,
            date_end=self.subscription_end_date,
            is_active=self.subscription_is_active,
            plan_version=plan_version
        )

    def setup_invoice(self, num_form_submitting_workers):
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_form_submitting_workers)

        invoice_date = utils.months_from_date(self.subscription.date_start, 2)
        record_date = invoice_date - datetime.timedelta(days=1)
        self._create_worker_history(DomainUserHistory, record_date)
        self._create_worker_history(FormSubmittingMobileWorkerHistory,
                                    record_date, num_workers=num_form_submitting_workers)

        tasks.generate_invoices_based_on_date(invoice_date)
        return self.subscription.invoice_set.latest('date_created')

    def _create_worker_history(self, history_cls, record_date, num_workers=0):
        history_cls.objects.create(
            domain=self.domain,
            record_date=record_date,
            num_users=num_workers
        )

    def test_under_limit(self):
        """
        When usage is not chargeable, the Form-Submitting Mobile Worker line item produced:
        - base_cost and unit_cost match FeatureRate defined on this test class
        - quantity is 0, because there were no excess users
        - unit_description is None, because its line item will not appear on invoice
        """
        num_form_submitting_workers = self.feature_rate.monthly_limit
        invoice = self.setup_invoice(num_form_submitting_workers)
        worker_line_item = invoice.lineitem_set.get_feature_by_type(
            FeatureType.FORM_SUBMITTING_MOBILE_WORKER).get()

        self.assertIsNone(worker_line_item.unit_description)
        self.assertEqual(worker_line_item.base_cost, self.feature_rate.monthly_fee)
        self.assertEqual(worker_line_item.unit_cost, self.feature_rate.per_excess_fee)
        self.assertEqual(worker_line_item.quantity, 0)

    def test_over_limit(self):
        """
        When usage is chargeable, the Form-Submitting Mobile Worker line item produced:
        - base_cost and unit_cost match the FeatureRate defined on this test class
        - quantity is the number of workers in excess of the FeatureRate's monthly_limit
        - unit_description includes 'form-submitting mobile worker'
        """
        num_excess = 3
        num_form_submitting_workers = self.feature_rate.monthly_limit + num_excess
        invoice = self.setup_invoice(num_form_submitting_workers)
        worker_line_item = invoice.lineitem_set.get_feature_by_type(
            FeatureType.FORM_SUBMITTING_MOBILE_WORKER).get()

        self.assertIn('form-submitting mobile worker', worker_line_item.unit_description)
        self.assertEqual(worker_line_item.quantity, num_excess)
        self.assertEqual(worker_line_item.base_cost, self.feature_rate.monthly_fee)
        self.assertEqual(worker_line_item.unit_cost, self.feature_rate.per_excess_fee)


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

        self.create_invoices(invoice_date, calculate_web_users=True)
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

        self.create_invoices(invoice_date, calculate_web_users=True)
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

        self.create_invoices(invoice_date, calculate_web_users=True)
        invoice = self.subscription.invoice_set.latest('date_created')
        self.assertEqual(invoice.lineitem_set.get_feature_by_type(FeatureType.WEB_USER).count(), 0)


class TestSmsLineItem(BaseInvoiceTestCase):
    is_using_test_plans = True

    @classmethod
    def setUpClass(cls):
        super(TestSmsLineItem, cls).setUpClass()
        cls.invoice_date = utils.months_from_date(
            cls.subscription_start_date, random.randint(2, cls.subscription_length)
        )
        cls.sms_date = utils.months_from_date(cls.invoice_date, -1)

    def setUp(self):
        super().setUp()
        self.sms_rate = self.subscription.plan_version.feature_rates.filter(
            feature__feature_type=FeatureType.SMS
        ).get()

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
        self.create_invoices(self.invoice_date)
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
