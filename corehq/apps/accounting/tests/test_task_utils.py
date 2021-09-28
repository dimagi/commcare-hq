import datetime
from collections import namedtuple
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from corehq.apps.accounting.task_utils import (
    get_context_to_send_purchase_receipt,
)
from corehq.apps.accounting.tasks import (
    get_context_to_send_autopay_failed_email,
)


class TestGetContextToSendAutopayFailedEmail(SimpleTestCase):

    def test_context_contains_expected_keys(self):
        invoice_id = 1

        with MockAutopayFailedInfo(invoice_id, web_user_email=None, auto_payer='auto-payer@dimagi.com'):
            context = get_context_to_send_autopay_failed_email(invoice_id)

        expected_keys = {'template_context', 'invoice_number', 'email_to', 'email_from'}
        self.assertEqual(set(context.keys()), expected_keys)

        expected_template_keys = {'domain', 'subscription_plan', 'billing_date', 'invoice_number', 'autopay_card',
                                  'domain_url', 'billing_info_url', 'support_email'}
        self.assertEqual(set(context['template_context'].keys()), expected_template_keys)

    def test_recipient_is_autopay_email_if_no_web_user_exists(self):
        invoice_id = 1

        with MockAutopayFailedInfo(invoice_id, web_user_email=None, auto_payer='auto-payer@dimagi.com'):
            context = get_context_to_send_autopay_failed_email(invoice_id)

        self.assertEqual(context['email_to'], 'auto-payer@dimagi.com')

    def test_recipient_is_web_users_email_if_web_user_exists(self):
        invoice_id = 1

        with MockAutopayFailedInfo(invoice_id, web_user_email='web-user@dimagi.com', auto_payer='username'):
            context = get_context_to_send_autopay_failed_email(invoice_id)

        self.assertEqual(context['email_to'], 'web-user@dimagi.com')

    def test_billing_url_is_correct(self):
        invoice_id = 1

        with MockAutopayFailedInfo(invoice_id, domain='test'):
            context = get_context_to_send_autopay_failed_email(invoice_id)

        template_context = context['template_context']
        self.assertTrue(
            template_context['billing_info_url'].endswith('/a/test/settings/project/billing_information/')
        )

    def test_domain_url_is_correct(self):
        invoice_id = 1

        with MockAutopayFailedInfo(invoice_id, domain='test'):
            context = get_context_to_send_autopay_failed_email(invoice_id)

        template_context = context['template_context']
        self.assertTrue(template_context['domain_url'].endswith('/a/test/dashboard/'))


class MockAutopayFailedInfo:
    def __init__(self, invoice_id, web_user_email=None, auto_payer=None, subscription_name=None, domain=None,
                 date=None):
        self.invoice_number = str(invoice_id)
        self.web_user_email = web_user_email

        self.subscription_name = subscription_name or 'test-subscription'
        self.auto_payer = auto_payer or 'test@dimagi.com'
        self.domain = domain or 'test-domain'
        self.date = date or datetime.date(2020, 1, 1)

    def __enter__(self):
        mock_invoice = MagicMock()
        mock_invoice.invoice_number = self.invoice_number
        mock_subscription = MagicMock()
        mock_subscription.plan_version.plan.name = self.subscription_name
        mock_subscription.account.auto_pay_user = self.auto_payer
        mock_invoice.subscription = mock_subscription
        mock_account = MagicMock()
        mock_invoice.account = mock_account
        mock_invoice.get_domain.return_value = self.domain

        self.invoice_patcher = patch(
            'corehq.apps.accounting.task_utils.Invoice.objects.get',
            return_value=mock_invoice
        )
        self.mock_get_invoice = self.invoice_patcher.start()

        mock_payment_method = MagicMock()
        MockCard = namedtuple('MockCard', 'brand last4 exp_month exp_year')
        mock_payment_method.get_autopay_card.return_value = MockCard(
            brand='Visa',
            last4='0000',
            exp_month='01',
            exp_year='01'
        )

        self.payment_method_patcher = patch(
            'corehq.apps.accounting.task_utils.StripePaymentMethod.objects.get',
            return_value=mock_payment_method
        )
        self.mock_payment_method = self.payment_method_patcher.start()

        mock_web_user = None
        if self.web_user_email:
            mock_web_user = MagicMock()
            mock_web_user.get_email.return_value = self.web_user_email
        self.web_user_patcher = patch(
            'corehq.apps.accounting.task_utils.WebUser.get_by_username',
            return_value=mock_web_user
        )
        self.web_user_patcher.start()

        self.datetime_patcher = patch('corehq.apps.accounting.task_utils.date')
        mock_date = self.datetime_patcher.start()
        mock_date.date.today.return_value = self.date

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.invoice_patcher.stop()
        self.payment_method_patcher.stop()
        self.web_user_patcher.stop()
        self.datetime_patcher.stop()


class TestGetContextToSendPurchaseReceipt(SimpleTestCase):

    def test_context_has_expected_keys(self):
        payment_record_id = 1
        domain = 'test'
        additional_context = {}

        with MockPurchaseReceiptInfo('username'):
            context = get_context_to_send_purchase_receipt(payment_record_id, domain, additional_context)

        expected_keys = {'template_context', 'email_to', 'email_from'}
        self.assertEqual(set(context.keys()), expected_keys)

    def test_template_context_has_expected_keys(self):
        payment_record_id = 1
        domain = 'test'
        additional_context = {}

        with MockPurchaseReceiptInfo('username'):
            context = get_context_to_send_purchase_receipt(payment_record_id, domain, additional_context)

        expected_template_keys = {'name', 'amount', 'project', 'date_paid', 'transaction_id'}
        self.assertEqual(set(context['template_context'].keys()), expected_template_keys)

    def test_template_context_has_additional_keys_if_supplied(self):
        payment_record_id = 1
        domain = 'test'
        additional_context = {'extra_key': 'extra_value'}

        with MockPurchaseReceiptInfo('username'):
            context = get_context_to_send_purchase_receipt(payment_record_id, domain, additional_context)

        expected_template_keys = {'name', 'amount', 'project', 'date_paid', 'transaction_id', 'extra_key'}
        self.assertEqual(set(context['template_context'].keys()), expected_template_keys)

    def test_recipient_is_web_user_if_web_user_exists(self):
        payment_record_id = 1
        domain = 'test'
        additional_context = {}

        with MockPurchaseReceiptInfo('username', web_user_email='web-user@dimagi.com'):
            context = get_context_to_send_purchase_receipt(payment_record_id, domain, additional_context)

        template_context = context['template_context']
        self.assertTrue(context['email_to'], 'web-user@dimagi.com')
        self.assertTrue(template_context['name'], 'web-user@dimagi.com')

    def test_recipient_is_username_if_web_user_does_not_exist(self):
        payment_record_id = 1
        domain = 'test'
        additional_context = {}

        with MockPurchaseReceiptInfo('username'):
            context = get_context_to_send_purchase_receipt(payment_record_id, domain, additional_context)

        template_context = context['template_context']
        self.assertTrue(context['email_to'], 'username')
        self.assertTrue(template_context['name'], 'username')

    def test_exception_is_logged_if_web_user_does_not_exist(self):
        payment_record_id = 1
        domain = 'test'
        additional_context = {}

        patcher = patch('corehq.apps.accounting.task_utils.raise_except_and_log_accounting_comms_error')
        mock_log_method = patcher.start()

        with MockPurchaseReceiptInfo('username'):
            get_context_to_send_purchase_receipt(payment_record_id, domain, additional_context)

        mock_log_method.assert_called()
        patcher.stop()


class MockPurchaseReceiptInfo:

    def __init__(self, username, web_user_email=None, date_paid=None, amount_paid=100):
        self.username = username
        self.web_user_email = web_user_email
        self.date_paid = date_paid or datetime.date(2020, 1, 1)
        self.amount_paid = amount_paid
        self.transaction_id = 1

    def __enter__(self):
        mock_payment_record = MagicMock()
        mock_payment_record.payment_method.web_user = self.username
        mock_payment_record.amount = self.amount_paid
        mock_payment_record.date_created = self.date_paid
        mock_payment_record.public_transaction_id = self.transaction_id

        self.payment_record_patcher = patch(
            'corehq.apps.accounting.task_utils.PaymentRecord.objects.get',
            return_value=mock_payment_record
        )
        self.payment_record_patcher.start()

        mock_web_user = None
        if self.web_user_email:
            mock_web_user = MagicMock()
            mock_web_user.get_email.return_value = self.web_user_email
        self.web_user_patcher = patch(
            'corehq.apps.accounting.task_utils.WebUser.get_by_username',
            return_value=mock_web_user
        )
        self.web_user_patcher.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.payment_record_patcher.stop()
        self.web_user_patcher.stop()
