import datetime

from corehq.apps.accounting.invoicing import (
    CustomerAccountInvoiceFactory,
    DomainInvoiceFactory,
    should_create_invoice,
)
from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    DomainUserHistory,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.utils import clear_plan_version_cache
from corehq.util.dates import get_previous_month_date_range


class TestDomainInvoiceFactory(BaseAccountingTest):

    @classmethod
    def setUpClass(cls):
        super(TestDomainInvoiceFactory, cls).setUpClass()
        generator.bootstrap_test_software_plan_versions()

    def setUp(self):
        super(TestDomainInvoiceFactory, self).setUp()
        self.invoice_start, self.invoice_end = get_previous_month_date_range()

        self.domain = generator.arbitrary_domain()
        self.account = BillingAccount.get_or_create_account_by_domain(
            domain=self.domain.name, created_by="TEST"
        )[0]
        self.community = DefaultProductPlan.get_default_plan_version()
        generator.arbitrary_commcare_users_for_domain(
            self.domain.name, self.community.user_limit + 1
        )

        self.invoice_factory = DomainInvoiceFactory(
            self.invoice_start, self.invoice_end, self.domain
        )

    def tearDown(self):
        self.domain.delete()
        super(TestDomainInvoiceFactory, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        clear_plan_version_cache()
        super(TestDomainInvoiceFactory, cls).tearDownClass()

    def test_feature_charges(self):
        domain_under_limits = generator.arbitrary_domain()
        self.assertTrue(self.community.feature_charges_exist_for_domain(self.domain))
        self.assertFalse(self.community.feature_charges_exist_for_domain(domain_under_limits))
        domain_under_limits.delete()

    def test_community_plan_generates_invoice(self):
        """
        Ensure that Community plans can generate invoices.
        """
        subscription = generator.generate_domain_subscription(
            self.account, self.domain, self.invoice_start, None,
            plan_version=generator.subscribable_plan_version(edition=SoftwarePlanEdition.COMMUNITY)
        )
        DomainUserHistory.objects.create(
            domain=self.domain.name, record_date=self.invoice_end, num_users=10)

        self.invoice_factory.create_invoices()
        invoice_count = subscription.invoice_set.count()
        self.assertEqual(invoice_count, 1)

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

        self.invoice_factory.create_invoices()
        invoice_count = subscription.invoice_set.count()
        self.assertEqual(invoice_count, 0)


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
