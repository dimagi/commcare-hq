import datetime
import random
from decimal import Decimal

from django.conf import settings
from django.core import mail
from django.test import override_settings

from corehq.apps.accounting import utils
from corehq.apps.accounting.const import SMALL_INVOICE_THRESHOLD
from corehq.apps.accounting.invoicing import (
    CustomerAccountInvoiceFactory,
    DomainInvoiceFactory,
    should_create_invoice,
)
from corehq.apps.accounting.models import (
    BillingAccount,
    BillingRecord,
    DefaultProductPlan,
    Invoice,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionType,
)
from corehq.apps.accounting.tasks import calculate_users_in_all_domains
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import (
    BaseAccountingTest,
    BaseInvoiceTestCase,
)
from corehq.apps.users.models import WebUser
from corehq.util.dates import get_previous_month_date_range


class TestInvoice(BaseInvoiceTestCase):
    """
    Tests that invoices are properly generated for the first month, last month, and a random month in the middle
    of a subscription for a domain.
    """

    def setUp(self):
        super().setUp()
        self.community = DefaultProductPlan.get_default_plan_version()
        generator.arbitrary_commcare_users_for_domain(
            self.domain.name, self.community.user_limit + 1
        )
        self.invoice_start, self.invoice_end = get_previous_month_date_range()

    def test_no_invoice_before_start(self):
        """
        No invoice gets created if the subscription didn't start in the previous month.
        """
        self.create_invoices(self.subscription.date_start, calculate_users=False)
        self.assertEqual(self.subscription.invoice_set.count(), 0)

    def test_subscription_invoice(self):
        invoice_date = utils.months_from_date(self.subscription.date_start,
                                              random.randint(2, self.subscription_length))
        self.create_invoices(invoice_date)
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
        self.create_invoices(invoice_date, calculate_users=False)
        self.assertEqual(self.subscription.invoice_set.count(), 0)

    def test_no_subscription_no_charges_no_invoice(self):
        """
        No invoices should be generated for domains that are not on a subscription and do not
        have any per_excess charges on users or SMS messages
        """
        self.create_invoices(datetime.date.today(), calculate_users=False)
        self.assertRaises(Invoice.DoesNotExist,
                          lambda: Invoice.objects.get(subscription__subscriber__domain=self.domain.name))

    def test_community_invoice(self):
        """
        For community-subscribed domain with any charges over the community limit for the month of invoicing,
        make sure that an invoice is generated.
        """
        today = datetime.date.today()
        generator.generate_domain_subscription(
            self.account, self.domain, self.subscription.date_start, None,
            plan_version=self.community
        )
        generator.create_excess_community_users(self.domain)
        self.account.date_confirmed_extra_charges = today
        self.account.save()
        self.create_invoices(datetime.date(today.year, today.month, 1))

        invoices = Invoice.objects.filter(subscription__subscriber__domain=self.domain.name)
        self.assertEqual(invoices.count(), 1)

        invoice = invoices.get()
        self.assertEqual(invoice.subscription.subscriber.domain, self.domain.name)

    def test_paused_plan_generates_no_invoice(self):
        """
        Ensure that Paused plans do not generate invoices.
        """
        paused_plan = generator.subscribable_plan_version(
            edition=SoftwarePlanEdition.PAUSED
        )
        subscription = Subscription.new_domain_subscription(
            self.account, self.domain.name, paused_plan,
            date_start=self.invoice_start,
            date_end=self.invoice_end + datetime.timedelta(days=1),
        )

        self.create_invoices(self.invoice_end, calculate_users=False)
        invoice_count = subscription.invoice_set.count()
        self.assertEqual(invoice_count, 0)

    def test_feature_charges(self):
        domain_under_limits = generator.arbitrary_domain()
        self.addCleanup(domain_under_limits.delete)

        self.assertTrue(self.community.feature_charges_exist_for_domain(self.domain))
        self.assertFalse(self.community.feature_charges_exist_for_domain(domain_under_limits))

    def test_date_due_not_set_small_invoice(self):
        """Date Due doesn't get set if the invoice is very small"""
        self.subscription.plan_version = generator.custom_plan_version(monthly_fee=1.00)
        self.subscription.save()
        invoice_date_small = utils.months_from_date(self.subscription.date_start, 1)
        self.create_invoices(invoice_date_small)
        small_invoice = self.subscription.invoice_set.first()

        self.assertTrue(small_invoice.balance <= SMALL_INVOICE_THRESHOLD)
        self.assertIsNone(small_invoice.date_due)

    def test_date_due_set_large_invoice(self):
        """Date Due only gets set for a 'large' invoice (> $1)"""
        self.subscription.plan_version = generator.subscribable_plan_version(SoftwarePlanEdition.ADVANCED)
        self.subscription.save()
        invoice_date_large = utils.months_from_date(self.subscription.date_start, 3)
        self.create_invoices(invoice_date_large)
        large_invoice = self.subscription.invoice_set.first()

        self.assertTrue(large_invoice.balance > SMALL_INVOICE_THRESHOLD)
        self.assertIsNotNone(large_invoice.date_due)

    def test_date_due_gets_set_autopay(self):
        """Date due gets set for autopay even if invoice is very small"""
        self.subscription.plan_version = generator.custom_plan_version(monthly_fee=1.00)
        self.subscription.save()
        self.subscription.account.update_autopay_user(self.billing_contact, self.domain)
        invoice_date_autopay = utils.months_from_date(self.subscription.date_start, 1)
        self.create_invoices(invoice_date_autopay)

        autopay_invoice = self.subscription.invoice_set.first()
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
        self.create_invoices(self.invoice_date)

        self.assertEqual(Invoice.objects.count(), 1)
        actual_recipient = Invoice.objects.first().email_recipients
        self.assertEqual(actual_recipient, expected_recipient)

    def test_contracted_invoice_email_template(self):
        """
        Emails for contracted invoices should use the contracted invoices template
        """
        expected_template = BillingRecord.INVOICE_CONTRACTED_HTML_TEMPLATE
        self.create_invoices(self.invoice_date)

        self.assertEqual(BillingRecord.objects.count(), 1)
        actual_template = BillingRecord.objects.first().html_template

        self.assertTrue(actual_template, expected_template)


class TestInvoiceRecipients(BaseInvoiceTestCase):

    def test_implementation_subscription_with_dimagi_contact(self):
        self._setup_implementation_subscription_with_dimagi_contact()

        invoice_date = utils.months_from_date(self.subscription.date_start, 1)
        self.create_invoices(invoice_date)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertListEqual(sent_email.to, ['dimagi_contact@test.com'])
        self.assertListEqual(sent_email.cc, [settings.ACCOUNTS_EMAIL])

    def test_implementation_subscription_without_dimagi_contact(self):
        self._setup_implementation_subscription_without_dimagi_contact()

        invoice_date = utils.months_from_date(self.subscription.date_start, 1)
        self.create_invoices(invoice_date)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertListEqual(sent_email.to, [settings.ACCOUNTS_EMAIL])
        self.assertListEqual(sent_email.cc, [])

    def test_product_subscription(self):
        self._setup_product_subscription()

        invoice_date = utils.months_from_date(self.subscription.date_start, 1)
        self.create_invoices(invoice_date)

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
        self.create_invoices(invoice_date)

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


class TestInvoicingMethods(BaseAccountingTest):

    def setUp(self):
        super(TestInvoicingMethods, self).setUp()
        self.invoice_start = datetime.date(2018, 5, 1)
        self.invoice_end = datetime.date(2018, 5, 31)

        self.domain = generator.arbitrary_domain()
        self.account = BillingAccount.get_or_create_account_by_domain(
            domain=self.domain, created_by="TEST"
        )[0]
        self.account.is_customer_billing_account = True
        self.account.save()
        self.invoice_factory = CustomerAccountInvoiceFactory(self.invoice_start, self.invoice_end, self.account)
        self.advanced_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.ADVANCED)
        self.advanced_plan.plan.is_customer_software_plan = True
        self.pro_plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.PRO)
        self.pro_plan.plan.is_customer_software_plan = True
        self.subscription = Subscription.new_domain_subscription(
            self.account,
            self.domain.name,
            self.advanced_plan,
            date_start=self.invoice_start,
            date_end=self.invoice_end
        )

    def tearDown(self):
        self.domain.delete()
        super(TestInvoicingMethods, self).tearDown()

    def test_should_not_invoice_trial(self):
        trial_domain = generator.arbitrary_domain()
        subscription = Subscription.new_domain_subscription(
            self.account, trial_domain.name, self.advanced_plan, date_start=self.invoice_start
        )
        subscription.is_trial = True
        self.assertFalse(should_create_invoice(
            subscription=subscription,
            domain=subscription.subscriber.domain,
            invoice_start=self.invoice_start,
            invoice_end=self.invoice_end
        ))
        trial_domain.delete()

    def test_should_not_invoice_paused_plan(self):
        """
        Ensure that paused plans do not generate a CustomerInvoice
        """
        paused_domain = generator.arbitrary_domain()
        self.addCleanup(paused_domain.delete)
        paused_plan = generator.subscribable_plan_version(
            edition=SoftwarePlanEdition.PAUSED
        )
        paused_plan.plan.is_customer_software_plan = True
        subscription = Subscription.new_domain_subscription(
            self.account, paused_domain.name, paused_plan,
            date_start=self.invoice_start,

        )
        self.assertFalse(should_create_invoice(
            subscription=subscription,
            domain=subscription.subscriber.domain,
            invoice_start=self.invoice_start,
            invoice_end=self.invoice_end
        ))

    def test_should_not_invoice_without_subscription_charges(self):
        feature_charge_domain = generator.arbitrary_domain()
        subscription = Subscription.new_domain_subscription(
            self.account, feature_charge_domain.name, self.advanced_plan, date_start=self.invoice_start
        )
        subscription.skip_invoicing_if_no_feature_charges = True
        self.assertFalse(should_create_invoice(
            subscription=subscription,
            domain=subscription.subscriber.domain,
            invoice_start=self.invoice_start,
            invoice_end=self.invoice_end
        ))
        feature_charge_domain.delete()

    def test_should_not_invoice_after_end(self):
        invoice_start = datetime.date(2018, 4, 1)
        invoice_end = datetime.date(2018, 4, 30)
        self.assertFalse(should_create_invoice(
            subscription=self.subscription,
            domain=self.subscription.subscriber.domain,
            invoice_start=invoice_start,
            invoice_end=invoice_end
        ))

    def test_should_not_invoice_before_start(self):
        invoice_start = datetime.date(2018, 6, 1)
        invoice_end = datetime.date(2018, 6, 30)
        self.assertFalse(should_create_invoice(
            subscription=self.subscription,
            domain=self.subscription.subscriber.domain,
            invoice_start=invoice_start,
            invoice_end=invoice_end
        ))
