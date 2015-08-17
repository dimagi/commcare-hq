from dateutil.relativedelta import relativedelta
import random

from corehq.apps.accounting.tasks import generate_invoices
from corehq.apps.accounting.forms import AdjustBalanceForm
from corehq.apps.accounting.models import (
    CreditAdjustmentReason,
    CreditLine,
    Invoice,
)
from corehq.apps.accounting.tests import BaseInvoiceTestCase


class TestAdjustBalanceForm(BaseInvoiceTestCase):
    def setUp(self):
        super(TestAdjustBalanceForm, self).setUp()
        generate_invoices(self.subscription.date_start + relativedelta(months=1))
        self.invoice = Invoice.objects.first()

    def tearDown(self):
        super(TestAdjustBalanceForm, self).tearDown()

    def test_manual_adjustment(self):
        original_balance = self.invoice.balance
        adjustment_amount = random.randint(1, 5)

        adjust_balance_form = AdjustBalanceForm(
            self.invoice,
            {
                'adjustment_type': 'credit',
                'custom_amount': adjustment_amount,
                'method': CreditAdjustmentReason.MANUAL,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        self.assertTrue(adjust_balance_form.is_valid())

        adjust_balance_form.adjust_balance()
        self.assertEqual(original_balance - adjustment_amount, self.invoice.balance)

    def test_transfer_credit_with_credit(self):
        original_credit_balance = random.randint(5, 10)
        CreditLine.add_credit(
            original_credit_balance,
            account=self.subscription.account,
            subscription=self.subscription,
        )
        original_balance = self.invoice.balance
        adjustment_amount = random.randint(1, 5)

        adjust_balance_form = AdjustBalanceForm(
            self.invoice,
            {
                'adjustment_type': 'credit',
                'custom_amount': adjustment_amount,
                'method': CreditAdjustmentReason.TRANSFER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        self.assertTrue(adjust_balance_form.is_valid())

        adjust_balance_form.adjust_balance()
        self.assertEqual(original_balance - adjustment_amount, self.invoice.balance)
        self.assertEqual(original_credit_balance - adjustment_amount, sum(
            credit_line.balance
            for credit_line in CreditLine.get_credits_for_invoice(self.invoice)
        ))

    def test_transfer_credit_without_credit(self):
        original_credit_balance = 0
        CreditLine.add_credit(
            original_credit_balance,
            account=self.subscription.account,
            subscription=self.subscription,
        )
        original_balance = self.invoice.balance
        adjustment_amount = random.randint(1, 5)

        adjust_balance_form = AdjustBalanceForm(
            self.invoice,
            {
                'adjustment_type': 'credit',
                'custom_amount': adjustment_amount,
                'method': CreditAdjustmentReason.TRANSFER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        self.assertTrue(adjust_balance_form.is_valid())

        adjust_balance_form.adjust_balance()
        self.assertEqual(original_balance, self.invoice.balance)
        self.assertEqual(original_credit_balance, sum(
            credit_line.balance
            for credit_line in CreditLine.get_credits_for_invoice(self.invoice)
        ))

    def test_transfer_debit_without_credit(self):
        original_credit_balance = 0
        CreditLine.add_credit(
            original_credit_balance,
            account=self.subscription.account,
            subscription=self.subscription,
        )
        original_balance = self.invoice.balance
        adjustment_amount = random.randint(1, 5)

        adjust_balance_form = AdjustBalanceForm(
            self.invoice,
            {
                'adjustment_type': 'debit',
                'custom_amount': adjustment_amount,
                'method': CreditAdjustmentReason.TRANSFER,
                'note': 'some text',
                'invoice_id': self.invoice.id,
            }
        )
        self.assertTrue(adjust_balance_form.is_valid())

        adjust_balance_form.adjust_balance()
        self.assertEqual(original_balance + adjustment_amount, self.invoice.balance)
        self.assertEqual(original_credit_balance + adjustment_amount, sum(
            credit_line.balance
            for credit_line in CreditLine.get_credits_for_invoice(self.invoice)
        ))
