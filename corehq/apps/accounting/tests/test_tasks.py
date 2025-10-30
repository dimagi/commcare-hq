import datetime
from unittest.mock import patch

from time_machine import travel

from corehq.apps.accounting import tasks
from corehq.apps.accounting.models import (
    FormSubmittingMobileWorkerHistory,
    SubscriptionAdjustment,
    SubscriptionAdjustmentMethod,
    SubscriptionType,
    WirePrepaymentBillingRecord,
    WirePrepaymentInvoice,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseInvoiceTestCase
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.form_processor.utils.xform import TestFormMetadata
from corehq.util.test_utils import flag_enabled, make_es_ready_form


@es_test(requires=[form_adapter], setup_class=True)
class TestCalculateFormSubmittingMobileWorkers(BaseInvoiceTestCase):

    def setUp(self):
        super().setUp()
        num_workers = 5
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_workers)

        self.num_form_submitting_workers = 3
        self.one_day_ago = datetime.date.today() - datetime.timedelta(days=1)
        one_week_ago_dt = datetime.datetime.combine(
            self.one_day_ago - datetime.timedelta(days=6), datetime.time()
        )
        for user in self.domain.all_users()[:self.num_form_submitting_workers]:
            self._submit_form(user, one_week_ago_dt)

    def _submit_form(self, user, received_on):
        form_pair = make_es_ready_form(
            TestFormMetadata(
                domain=self.domain.name,
                user_id=user.user_id,
                received_on=received_on
            )
        )
        form_adapter.index(form_pair.json_form, refresh=True)

    def tearDown(self):
        delete_all_users()
        delete_all_domains()
        return super().tearDown()

    def test_calculate_form_submitting_mobile_workers_in_all_domains(self):
        tasks.calculate_form_submitting_mobile_workers_in_all_domains()
        self.assertEqual(FormSubmittingMobileWorkerHistory.objects.count(), 1)

        worker_history = FormSubmittingMobileWorkerHistory.objects.first()
        self.assertEqual(worker_history.domain, self.domain.name)
        self.assertEqual(worker_history.num_users, self.num_form_submitting_workers)
        self.assertEqual(worker_history.record_date, self.one_day_ago)


@travel('2025-10-01', tick=False)
@flag_enabled('SHOW_AUTO_RENEWAL')
class TestSubscriptionReminderEmails(BaseInvoiceTestCase):

    def test_sends_renewal_reminder_email(self):
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=60)
        self.subscription.service_type = SubscriptionType.PRODUCT
        self.subscription.save()

        with patch('corehq.apps.accounting.tasks.send_renewal_reminder_email') as mock_send:
            tasks.send_renewal_reminder_emails(60)
            mock_send.assert_called_once_with(self.subscription, 60)

    def test_no_renewal_reminder_if_service_type_not_product(self):
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=60)
        self.subscription.service_type = SubscriptionType.IMPLEMENTATION
        self.subscription.save()

        with patch('corehq.apps.accounting.tasks.send_renewal_reminder_email') as mock_send:
            tasks.send_renewal_reminder_emails(60)
            assert not mock_send.called

    def test_no_renewal_reminder_if_is_trial(self):
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=60)
        self.subscription.is_trial = True
        self.subscription.save()

        with patch('corehq.apps.accounting.tasks.send_renewal_reminder_email') as mock_send:
            tasks.send_renewal_reminder_emails(60)
            assert not mock_send.called

    def test_no_renewal_reminder_if_customer_billing_account(self):
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=60)
        self.subscription.account.is_customer_billing_account = True
        self.subscription.account.save()
        self.subscription.save()

        with patch('corehq.apps.accounting.tasks.send_renewal_reminder_email') as mock_send:
            tasks.send_renewal_reminder_emails(60)
            assert not mock_send.called

    def test_no_renewal_reminder_if_is_renewed(self):
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=59)
        self.subscription.renew_subscription()
        self.subscription.save()

        with patch('corehq.apps.accounting.tasks.send_renewal_reminder_email') as mock_send:
            tasks.send_renewal_reminder_emails(60)
            assert not mock_send.called

    def test_sends_subscription_ending_email(self):
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=60)
        self.subscription.service_type = SubscriptionType.PRODUCT
        self.subscription.save()

        with patch('corehq.apps.accounting.tasks.send_subscription_ending_email') as mock_send:
            tasks.send_subscription_ending_emails(60)
            mock_send.assert_called_once_with(self.subscription, 60)

    def test_no_subscription_ending_email_if_auto_renew_enabled(self):
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=60)
        self.subscription.service_type = SubscriptionType.PRODUCT
        self.subscription.auto_renew = True
        self.subscription.save()

        with patch('corehq.apps.accounting.tasks.send_subscription_ending_email') as mock_send:
            tasks.send_subscription_ending_emails(60)
            assert not mock_send.called

    def test_no_subscription_ending_email_if_service_type_not_product(self):
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=60)
        self.subscription.service_type = SubscriptionType.IMPLEMENTATION
        self.subscription.save()

        with patch('corehq.apps.accounting.tasks.send_subscription_ending_email') as mock_send:
            tasks.send_subscription_ending_emails(60)
            assert not mock_send.called

    def test_no_subscription_ending_email_if_is_trial(self):
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=60)
        self.subscription.is_trial = True
        self.subscription.save()

        with patch('corehq.apps.accounting.tasks.send_subscription_ending_email') as mock_send:
            tasks.send_subscription_ending_emails(60)
            assert not mock_send.called

    def test_no_subscription_ending_email_if_customer_billing_account(self):
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=60)
        self.subscription.account.is_customer_billing_account = True
        self.subscription.account.save()
        self.subscription.save()

        with patch('corehq.apps.accounting.tasks.send_subscription_ending_email') as mock_send:
            tasks.send_subscription_ending_emails(60)
            assert not mock_send.called

    def test_no_subscription_ending_email_if_is_renewed(self):
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=60)
        self.subscription.renew_subscription()
        self.subscription.save()

        with patch('corehq.apps.accounting.tasks.send_subscription_ending_email') as mock_send:
            tasks.send_subscription_ending_emails(60)
            assert not mock_send.called


@travel('2025-10-01', tick=False)
class TestAutoRenewableSubscriptions(BaseInvoiceTestCase):

    def test_includes_subscription_exactly_30_days_left(self):
        self._set_auto_renew_properties(
            date_end=datetime.date.today() + datetime.timedelta(days=30)
        )
        subscriptions = tasks._get_auto_renewable_subscriptions()
        assert self.subscription in subscriptions

    def test_includes_subscription_less_than_30_days_left(self):
        self._set_auto_renew_properties(date_end=datetime.date.today())
        subscriptions = tasks._get_auto_renewable_subscriptions()
        assert self.subscription in subscriptions

    def test_excludes_subscription_more_than_30_days_left(self):
        self._set_auto_renew_properties(
            date_end=datetime.date.today() + datetime.timedelta(days=31)
        )
        subscriptions = tasks._get_auto_renewable_subscriptions()
        assert self.subscription not in subscriptions

    def test_excludes_subscription_end_date_in_past(self):
        self._set_auto_renew_properties(
            date_end=datetime.date.today() - datetime.timedelta(days=1)
        )
        subscriptions = tasks._get_auto_renewable_subscriptions()
        assert self.subscription not in subscriptions

    def test_excludes_auto_renew_false(self):
        self._set_auto_renew_properties(
            auto_renew=False,
        )
        subscriptions = tasks._get_auto_renewable_subscriptions()
        assert self.subscription not in subscriptions

    def test_excludes_service_type_not_product(self):
        self._set_auto_renew_properties(
            service_type=SubscriptionType.IMPLEMENTATION,
        )
        subscriptions = tasks._get_auto_renewable_subscriptions()
        assert self.subscription not in subscriptions

    def test_excludes_customer_billing_account(self):
        self._set_auto_renew_properties(
            is_customer_billing_account=True,
        )
        subscriptions = tasks._get_auto_renewable_subscriptions()
        assert self.subscription not in subscriptions

    def test_auto_renew_ignores_already_renewed(self):
        self._set_auto_renew_properties()
        self.subscription.renew_subscription()
        with patch('corehq.apps.accounting.tasks.auto_renew_subscription') as mock_renew:
            tasks.auto_renew_subscriptions()
            assert not mock_renew.called

    def _set_auto_renew_properties(
        self,
        date_end=datetime.date.today() + datetime.timedelta(days=30),
        service_type=SubscriptionType.PRODUCT,
        auto_renew=True,
        is_customer_billing_account=False,
    ):
        self.subscription.date_end = date_end
        self.subscription.service_type = service_type
        self.subscription.auto_renew = auto_renew
        self.subscription.save()

        self.account.is_customer_billing_account = is_customer_billing_account
        self.account.save()


class TestAutoRenewSubscription(BaseInvoiceTestCase):

    def setUp(self):
        super().setUp()
        self.subscription.date_end = datetime.date.today() + datetime.timedelta(days=30)
        self.subscription.service_type = SubscriptionType.PRODUCT
        self.subscription.auto_renew = True
        self.subscription.save()

        self.account.is_customer_billing_account = False
        self.account.save()

    def test_auto_renew_subscription(self):
        with patch('corehq.apps.accounting.tasks.send_subscription_renewed_email') as mock_send:
            tasks.auto_renew_subscription(self.subscription)

        next_subscription = self.subscription.next_subscription
        mock_send.assert_called_once_with(next_subscription)
        assert self.subscription.is_renewed
        assert next_subscription.date_start == self.subscription.date_end
        next_plan = next_subscription.plan_version.plan
        assert next_plan.edition == self.subscription.plan_version.plan.edition
        assert next_plan.is_annual_plan == self.subscription.plan_version.plan.is_annual_plan

        subscription_adjustment = SubscriptionAdjustment.objects.get(
            subscription=self.subscription,
            related_subscription=next_subscription,
        )
        assert subscription_adjustment.method == SubscriptionAdjustmentMethod.AUTO_RENEWAL

    def test_creates_prepayment_invoice_if_is_annual_plan(self):
        self.subscription.plan_version.plan.is_annual_plan = True
        self.subscription.plan_version.plan.save()
        tasks.auto_renew_subscription(self.subscription)

        prepayment_invoices = WirePrepaymentInvoice.objects.filter(domain=self.domain.name)
        assert prepayment_invoices.count() == 1
        prepayment_invoice = prepayment_invoices.get()
        assert WirePrepaymentBillingRecord.objects.filter(invoice=prepayment_invoice).exists()
