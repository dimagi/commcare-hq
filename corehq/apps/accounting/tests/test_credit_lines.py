from decimal import Decimal
import random
from corehq.apps.accounting import tasks, utils, generator
from corehq.apps.accounting.models import CreditLine, CreditAdjustment, FeatureType
from corehq.apps.accounting.tests import BaseInvoiceTestCase


class TestCreditLines(BaseInvoiceTestCase):
    min_subscription_length = 5

    def setUp(self):
        super(TestCreditLines, self).setUp()
        self.product_rate = self.subscription.plan_version.product_rates.get()
        self.user_rate = self.subscription.plan_version.feature_rates.filter(feature__feature_type=FeatureType.USER)[:1].get()
        num_active = random.randint(self.user_rate.monthly_limit + 1, self.user_rate.monthly_limit + 2)
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_active)
        num_excess = num_active - self.user_rate.monthly_limit
        self.monthly_user_fee = num_excess * self.user_rate.per_excess_fee

    def test_product_line_item_credits(self):
        """
        Make sure that the product line item Credit Lines are properly created and that the appropriate
        CreditAdjustments are being recorded. Also that available credit lines are being applied to the
        invoices properly.
        """
        rate_credit_by_account = CreditLine.add_product_credit(
            self.product_rate.monthly_fee, self.account,
            self.product_rate.product.product_type
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=rate_credit_by_account).count(), 1
        )

        rate_credit_by_subscription = CreditLine.add_product_credit(
            self.product_rate.monthly_fee, self.account,
            self.product_rate.product.product_type,
            subscription=self.subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=rate_credit_by_subscription,
        ).count(), 1)

        subscription_credit = CreditLine.add_subscription_credit(
            self.product_rate.monthly_fee,
            self.subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=subscription_credit).count(), 1
        )

        self._test_line_item_crediting(
            lambda invoice: invoice.lineitem_set.get_products().get()
        )
        self._test_credit_use(rate_credit_by_account)
        self._test_credit_use(rate_credit_by_subscription)
        self._clean_credits()

    def test_feature_line_item_credits(self):
        """
        Make sure that the feature line item Credit Lines are properly created and that the appropriate
        CreditAdjustments are being recorded. Also that available credit lines are being applied to the
        invoices properly.
        """
        rate_credit_by_account = CreditLine.add_feature_credit(
            self.monthly_user_fee, self.account,
            self.user_rate.feature.feature_type,
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=rate_credit_by_account).count(), 1
        )

        rate_credit_by_subscription = CreditLine.add_feature_credit(
            self.monthly_user_fee, self.account,
            self.user_rate.feature.feature_type,
            subscription=self.subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=rate_credit_by_subscription
        ).count(), 1)

        subscription_credit = CreditLine.add_subscription_credit(
            self.monthly_user_fee,
            self.subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=subscription_credit).count(), 1
        )

        self._test_line_item_crediting(
            lambda invoice: invoice.lineitem_set.get_feature_by_type(FeatureType.USER).get()
        )
        self._test_credit_use(rate_credit_by_account)
        self._test_credit_use(rate_credit_by_subscription)
        self._clean_credits()

    def _generate_users_fee_to_credit_against(self):
        user_rate = self.subscription.plan_version.feature_rates.filter(feature__feature_type=FeatureType.USER)[:1].get()
        num_active = random.randint(user_rate.monthly_limit + 1, user_rate.monthly_limit + 2)
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_active)
        num_excess = num_active - user_rate.monthly_limit
        per_month_fee = num_excess * user_rate.per_excess_fee
        return user_rate, per_month_fee

    def _test_line_item_crediting(self, get_line_item_from_invoice):
        """
        Tests line item credits for three invoicing periods.
        """
        for month_num in range(2, 5):
            invoice_date = utils.months_from_date(self.subscription.date_start, month_num)
            tasks.generate_invoices(invoice_date)
            invoice = self.subscription.invoice_set.latest('date_end')

            line_item = get_line_item_from_invoice(invoice)
            if month_num < 4:
                # the first two invoices for the line item should be covered by its credit line
                self.assertEqual(line_item.total, Decimal('0.0000'))
            else:
                self.assertNotEqual(line_item.total, Decimal('0.0000'))

    def _test_credit_use(self, credit_line):
        """
        Makes sure that the line item credits were used properly.
        """
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=credit_line).count(), 2)
        self.assertEqual(CreditLine.objects.get(id=credit_line.id).balance, Decimal('0.0000'))

    def test_invoice_credit(self):
        """
        Make sure that subscription and account level credits get applied to the invoice balance appropriately.
        """
        invoice_monthly_total = self.product_rate.monthly_fee + self.monthly_user_fee

        subscription_credit, account_credit = self._generate_subscription_and_account_invoice_credits(
            invoice_monthly_total, self.subscription, self.account
        )

        # other subscription credit that shouldn't count toward this invoice
        other_domain = generator.arbitrary_domain()
        # so that the other subscription doesn't draw from the same account credits, have it start 4 months later
        new_subscription_start = utils.months_from_date(self.subscription.date_start, 4)
        other_subscription, _ = generator.generate_domain_subscription_from_date(
            new_subscription_start, self.account, other_domain.name, min_num_months=self.min_subscription_length,
        )
        # other account credit that shouldn't count toward this invoice
        other_account = generator.billing_account(self.dimagi_user, generator.arbitrary_web_user())

        self._generate_subscription_and_account_invoice_credits(
            invoice_monthly_total, other_subscription, other_account
        )

        self._test_final_invoice_balance()

        self._test_credit_use(subscription_credit)
        self._test_credit_use(account_credit)
        self._clean_credits()

    def test_combined_credits(self):
        """
        Test that line item credits get applied first to the line items
        and invoice credits get applied to the remaining balance.
        """
        self._clean_credits()

        user_rate_credit_by_account = CreditLine.add_feature_credit(
            self.monthly_user_fee, self.account,
            self.user_rate.feature.feature_type,
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=user_rate_credit_by_account).count(), 1
        )

        user_rate_credit_by_subscription = CreditLine.add_feature_credit(
            self.monthly_user_fee, self.account,
            self.user_rate.feature.feature_type,
            subscription=self.subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=user_rate_credit_by_subscription
        ).count(), 1)

        subscription_credit, account_credit = self._generate_subscription_and_account_invoice_credits(
            self.product_rate.monthly_fee, self.subscription, self.account
        )

        self._test_final_invoice_balance()

        self._test_credit_use(subscription_credit)
        self._test_credit_use(user_rate_credit_by_subscription)
        self._test_credit_use(subscription_credit)
        self._test_credit_use(account_credit)
        self._clean_credits()

    def _generate_subscription_and_account_invoice_credits(self, monthly_fee, subscription, account):
        subscription_credit = CreditLine.add_subscription_credit(
            monthly_fee,
            subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=subscription_credit).count(), 1)

        account_credit = CreditLine.add_account_credit(
            monthly_fee,
            account
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=account_credit).count(), 1)
        return subscription_credit, account_credit

    def _test_final_invoice_balance(self):
        for month_num in range(2, 5):
            invoice_date = utils.months_from_date(self.subscription.date_start, month_num)
            tasks.generate_invoices(invoice_date)
            invoice = self.subscription.invoice_set.latest('date_end')

            if month_num < 4:
                # the first two invoices for the line item should be covered by its credit line
                self.assertEqual(invoice.balance, Decimal('0.0000'))
            else:
                self.assertNotEqual(invoice.balance, Decimal('0.0000'))

    def test_balance_adjustment(self):
        """
        Makes sure that the balance is added to the same invoice and same line item credit.
        """
        product_credit = CreditLine.add_product_credit(
            self.product_rate.monthly_fee, self.account,
            self.product_rate.product.product_type,
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=product_credit).count(), 1)
        CreditLine.add_product_credit(
            self.product_rate.monthly_fee, self.account,
            self.product_rate.product.product_type,
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=product_credit).count(), 2)
        current_product_credit = CreditLine.objects.get(id=product_credit.id)
        self.assertEqual(current_product_credit.balance, self.product_rate.monthly_fee * 2)

        subscription_credit = CreditLine.add_subscription_credit(
            self.monthly_user_fee,
            self.subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=subscription_credit).count(), 1)
        CreditLine.add_subscription_credit(
            self.monthly_user_fee,
            self.subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=subscription_credit).count(), 2)
        current_subscription_credit = CreditLine.objects.get(id=subscription_credit.id)
        self.assertEqual(current_subscription_credit.balance, self.monthly_user_fee * 2)

        account_credit = CreditLine.add_account_credit(
            self.product_rate.monthly_fee,
            self.account
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=account_credit).count(), 1)
        CreditLine.add_account_credit(
            self.monthly_user_fee,
            self.account
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=account_credit).count(), 2)
        current_account_credit = CreditLine.objects.get(id=account_credit.id)
        self.assertEqual(current_account_credit.balance, self.product_rate.monthly_fee + self.monthly_user_fee)

    def _clean_credits(self):
        CreditAdjustment.objects.all().delete()
        CreditLine.objects.all().delete()
