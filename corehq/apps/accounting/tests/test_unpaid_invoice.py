import datetime
from unittest.mock import patch

from corehq.apps.accounting import tasks, utils
from corehq.apps.accounting.const import (
    DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER,
    DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE,
    DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE_WARNING,
    DAYS_PAST_DUE_TO_TRIGGER_OVERDUE_NOTICE,
)
from corehq.apps.accounting.models import (
    CommunicationType,
    CustomerInvoice,
    CustomerInvoiceCommunicationHistory,
    DefaultProductPlan,
    DomainUserHistory,
    InvoiceCommunicationHistory,
    SoftwarePlanEdition,
    Subscription,
    SubscriptionType,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.utils.unpaid_invoice import Downgrade, InvoiceReminder


def _generate_invoice_and_subscription(days_ago, is_customer_billing_account=False):
    """
    :param days_ago: The number of days ago an invoice should be due
    :return: random domain, with invoices generated on the backend
    """
    invoice_due_date = datetime.date.today() - datetime.timedelta(days=days_ago)

    billing_contact = generator.create_arbitrary_web_user_name()
    dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
    account = generator.billing_account(
        dimagi_user,
        billing_contact
    )
    account.is_customer_billing_account = is_customer_billing_account
    account.save()

    domain = generator.arbitrary_domain()
    subscription_start_date = utils.months_from_date(invoice_due_date, -2)

    subscription = generator.generate_domain_subscription(
        account,
        domain,
        date_start=subscription_start_date,
        date_end=None,
        plan_version=DefaultProductPlan.get_default_plan_version(
            SoftwarePlanEdition.ADVANCED
        ),
        service_type=SubscriptionType.PRODUCT,
    )
    subscription.is_active = True
    subscription.save()

    invoice_date = utils.months_from_date(invoice_due_date, -1)
    DomainUserHistory.objects.create(
        domain=domain.name,
        num_users=20,
        record_date=invoice_date - datetime.timedelta(days=1)
    )
    tasks.generate_invoices_based_on_date(invoice_date)

    # for testing purposes, force the latest invoice due_date to be
    # the "invoice_due_date" specified above
    if is_customer_billing_account:
        latest_invoice = CustomerInvoice.objects.filter(
            account=account,
        ).latest('date_created')
    else:
        latest_invoice = subscription.invoice_set.latest('date_created')
    latest_invoice.date_due = invoice_due_date
    latest_invoice.save()

    return domain, latest_invoice


class TestDowngrades(BaseAccountingTest):

    @classmethod
    def setUpClass(cls):
        super(TestDowngrades, cls).setUpClass()
        generator.bootstrap_test_software_plan_versions()
        generator.init_default_currency()

    def setUp(self):
        super(TestDowngrades, self).setUp()
        self.domains = []

    def tearDown(self):
        for domain in self.domains:
            for user in domain.all_users():
                user.delete(domain.name, deleted_by=None)
            domain.delete()
        super(BaseAccountingTest, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        utils.clear_plan_version_cache()
        super(TestDowngrades, cls).tearDownClass()

    def _simulate_downgrade(self, days_overdue, is_customer_billing_account=False):
        domain, latest_invoice = _generate_invoice_and_subscription(
            days_overdue,
            is_customer_billing_account=is_customer_billing_account
        )
        self.domains.append(domain)
        Downgrade.run_action(only_downgrade_domain=domain.name)
        return domain, latest_invoice

    def test_no_notification(self):
        domain, latest_invoice = self._simulate_downgrade(
            DAYS_PAST_DUE_TO_TRIGGER_OVERDUE_NOTICE - 1
        )
        self.assertFalse(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
        ).exists())

    def test_overdue_notification(self):
        domain, latest_invoice = self._simulate_downgrade(
            DAYS_PAST_DUE_TO_TRIGGER_OVERDUE_NOTICE
        )

        # confirm communication was initiated
        self.assertTrue(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.OVERDUE_INVOICE,
        ).exists())

        # try to trigger another communication (it should fail), and make sure
        # only one communication was ever sent
        Downgrade.run_action(only_downgrade_domain=domain.name)
        self.assertTrue(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
        ).count(), 1)

    def test_belated_overdue_notification(self):
        # just in case on the 30th day, the downgrade process fails, make
        # sure it happens properly on the 31st day.
        domain, latest_invoice = self._simulate_downgrade(
            DAYS_PAST_DUE_TO_TRIGGER_OVERDUE_NOTICE + 1
        )

        # confirm communication was initiated
        self.assertTrue(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.OVERDUE_INVOICE,
        ).exists())

    def test_downgrade_warning(self):
        domain, latest_invoice = self._simulate_downgrade(
            DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE_WARNING
        )

        # confirm communication was initiated
        self.assertTrue(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.DOWNGRADE_WARNING,
        ).exists())

        # make sure a downgrade warning isn't sent again
        Downgrade.run_action(only_downgrade_domain=domain.name)
        self.assertTrue(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.DOWNGRADE_WARNING,
        ).count(), 1)

    def test_downgrade(self):
        domain, latest_invoice = self._simulate_downgrade(
            DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE
        )

        # confirm a downgrade wasn't actually initiated because a warning
        # email has not been sent
        subscription = Subscription.get_active_subscription_by_domain(domain)
        self.assertNotEqual(subscription.plan_version.plan.edition, SoftwarePlanEdition.PAUSED)

        # fake the warning to have been triggered a few days ago
        warning_days_ago = DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE - DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE_WARNING
        history = InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice
        ).latest('date_created')
        history.date_created = datetime.date.today() - datetime.timedelta(days=warning_days_ago)
        history.save()

        # now trigger a successful downgrade
        Downgrade.run_action(only_downgrade_domain=domain.name)
        subscription = Subscription.get_active_subscription_by_domain(domain)
        self.assertEqual(subscription.plan_version.plan.edition, SoftwarePlanEdition.PAUSED)

    def test_overdue_customer_notification(self):
        domain, latest_invoice = self._simulate_downgrade(
            DAYS_PAST_DUE_TO_TRIGGER_OVERDUE_NOTICE,
            is_customer_billing_account=True
        )
        # confirm communication was initiated
        self.assertTrue(CustomerInvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.OVERDUE_INVOICE,
        ).exists())

    def test_overdue_customer_downgrade_warning(self):
        domain, latest_invoice = self._simulate_downgrade(
            DAYS_PAST_DUE_TO_TRIGGER_DOWNGRADE_WARNING,
            is_customer_billing_account=True
        )
        # confirm communication was initiated
        self.assertTrue(CustomerInvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.DOWNGRADE_WARNING,
        ).exists())


class TestInvoiceReminder(BaseAccountingTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        generator.bootstrap_test_software_plan_versions()
        generator.init_default_currency()

    def setUp(self):
        super().setUp()
        self.domains = []

    def tearDown(self):
        for domain in self.domains:
            for user in domain.all_users():
                user.delete(domain.name, deleted_by=None)
            domain.delete()
        super().tearDown()

    @classmethod
    def tearDownClass(cls):
        utils.clear_plan_version_cache()
        super().tearDownClass()

    def _send_invoice_reminders(self, days_before_due, is_customer_billing_account=False):
        domain, latest_invoice = self._setup_invoices(
            days_before_due, is_customer_billing_account=is_customer_billing_account)
        self._run_action()
        return domain, latest_invoice

    def _setup_invoices(self, days_before_due, is_customer_billing_account=False):
        domain, latest_invoice = _generate_invoice_and_subscription(
            -(days_before_due),
            is_customer_billing_account=is_customer_billing_account
        )
        self.domains.append(domain)
        return domain, latest_invoice

    @staticmethod
    def _run_action():
        InvoiceReminder.run_action()

    def test_invoice_reminder(self):
        domain, latest_invoice = self._send_invoice_reminders(
            DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER
        )

        # confirm communication was initiated
        self.assertTrue(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.INVOICE_REMINDER,
        ).exists())

        # make sure an invoice reminder isn't sent again
        InvoiceReminder.run_action()
        self.assertTrue(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.INVOICE_REMINDER,
        ).count(), 1)

    def test_belated_invoice_reminder(self):
        domain, latest_invoice = self._send_invoice_reminders(
            DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER - 1,
        )

        self.assertTrue(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.INVOICE_REMINDER,
        ).exists())

    def test_invoice_reminder_not_sent_early(self):
        domain, latest_invoice = self._send_invoice_reminders(
            DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER + 1,
        )

        self.assertFalse(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.INVOICE_REMINDER,
        ).exists())

    def test_no_reminder_if_not_should_send_email(self):
        with patch('corehq.apps.accounting.models.BillingRecord.should_send_email', False):
            domain, latest_invoice = self._send_invoice_reminders(
                DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER,
            )

        self.assertFalse(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.INVOICE_REMINDER,
        ).exists())

    def test_no_reminder_if_skipped_email(self):
        domain, latest_invoice = self._setup_invoices(
            DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER,
        )
        billing_record = latest_invoice.billingrecord_set.first()
        billing_record.skipped_email = True
        billing_record.save()
        self._run_action()

        self.assertFalse(InvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.INVOICE_REMINDER,
        ).exists())

    def test_customer_invoice_reminder(self):
        domain, latest_invoice = self._send_invoice_reminders(
            DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER,
            is_customer_billing_account=True,
        )

        # confirm communication was initiated
        self.assertTrue(CustomerInvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.INVOICE_REMINDER,
        ).exists())

        # make sure an invoice reminder isn't sent again
        InvoiceReminder.run_action()
        self.assertTrue(CustomerInvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.INVOICE_REMINDER,
        ).count(), 1)

    def test_belated_customer_invoice_reminder(self):
        domain, latest_invoice = self._send_invoice_reminders(
            DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER - 1,
            is_customer_billing_account=True,
        )

        self.assertTrue(CustomerInvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.INVOICE_REMINDER,
        ).exists())

    def test_customer_invoice_reminder_not_sent_early(self):
        domain, latest_invoice = self._send_invoice_reminders(
            DAYS_BEFORE_DUE_TO_TRIGGER_REMINDER + 1,
            is_customer_billing_account=True,
        )

        self.assertFalse(CustomerInvoiceCommunicationHistory.objects.filter(
            invoice=latest_invoice,
            communication_type=CommunicationType.INVOICE_REMINDER,
        ).exists())
