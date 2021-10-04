import datetime
import random
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from dimagi.utils.dates import add_months_to_date

from corehq.apps.accounting import tasks, utils
from corehq.apps.accounting.models import (
    BillingAccount,
    CreditAdjustment,
    CreditAdjustmentReason,
    CreditLine,
    DefaultProductPlan,
    FeatureType,
    SoftwarePlanEdition,
    Subscription,
    DomainUserHistory,
)
from corehq.apps.accounting.tasks import deactivate_subscriptions
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase


class TestCreditLines(BaseInvoiceTestCase):

    is_using_test_plans = True
    min_subscription_length = 5

    @classmethod
    def setUpClass(cls):
        super(TestCreditLines, cls).setUpClass()
        cls.product_rate = cls.subscription.plan_version.product_rate
        cls.user_rate = cls.subscription.plan_version.feature_rates.filter(feature__feature_type=FeatureType.USER)[:1].get()

    def setUp(self):
        super(TestCreditLines, self).setUp()
        num_active = random.randint(self.user_rate.monthly_limit + 1, self.user_rate.monthly_limit + 2)
        generator.arbitrary_commcare_users_for_domain(self.domain.name, num_active)
        num_excess = num_active - self.user_rate.monthly_limit
        self.monthly_user_fee = num_excess * self.user_rate.per_excess_fee

    def tearDown(self):
        for user in self.domain.all_users():
            user.delete(self.domain.name, deleted_by=None)
        super(TestCreditLines, self).tearDown()

    def test_product_line_item_credits(self):
        """
        Make sure that the product line item Credit Lines are properly created and that the appropriate
        CreditAdjustments are being recorded. Also that available credit lines are being applied to the
        invoices properly.
        """
        rate_credit_by_account = CreditLine.add_credit(
            self.product_rate.monthly_fee, account=self.account,
            is_product=True
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=rate_credit_by_account).count(), 1
        )

        rate_credit_by_subscription = CreditLine.add_credit(
            self.product_rate.monthly_fee,
            is_product=True,
            subscription=self.subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=rate_credit_by_subscription,
        ).count(), 1)

        subscription_credit = CreditLine.add_credit(
            self.product_rate.monthly_fee, subscription=self.subscription,
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=subscription_credit).count(), 1
        )

        self._test_line_item_crediting(
            lambda invoice: invoice.lineitem_set.get_products().get()
        )
        self._test_credit_use(rate_credit_by_account)
        self._test_credit_use(rate_credit_by_subscription)

    def test_feature_line_item_credits(self):
        """
        Make sure that the feature line item Credit Lines are properly created and that the appropriate
        CreditAdjustments are being recorded. Also that available credit lines are being applied to the
        invoices properly.
        """
        rate_credit_by_account = CreditLine.add_credit(
            self.monthly_user_fee, account=self.account,
            feature_type=self.user_rate.feature.feature_type,
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=rate_credit_by_account).count(), 1
        )

        rate_credit_by_subscription = CreditLine.add_credit(
            self.monthly_user_fee,
            feature_type=self.user_rate.feature.feature_type,
            subscription=self.subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=rate_credit_by_subscription
        ).count(), 1)

        subscription_credit = CreditLine.add_credit(
            self.monthly_user_fee, subscription=self.subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=subscription_credit).count(), 1
        )

        self._test_line_item_crediting(
            lambda invoice: invoice.lineitem_set.get_feature_by_type(FeatureType.USER).get()
        )
        self._test_credit_use(rate_credit_by_account)
        self._test_credit_use(rate_credit_by_subscription)

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
            tasks.calculate_users_in_all_domains(invoice_date)
            tasks.generate_invoices_based_on_date(invoice_date)
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

        other_subscription = generator.generate_domain_subscription(
            self.account,
            other_domain,
            date_start=new_subscription_start,
            date_end=add_months_to_date(new_subscription_start, self.min_subscription_length),
        )

        # other account credit that shouldn't count toward this invoice
        other_account = generator.billing_account(self.dimagi_user, generator.create_arbitrary_web_user_name())

        self._generate_subscription_and_account_invoice_credits(
            invoice_monthly_total, other_subscription, other_account
        )

        self._test_final_invoice_balance()

        self._test_credit_use(subscription_credit)
        self._test_credit_use(account_credit)
        other_domain.delete()

    def test_combined_credits(self):
        """
        Test that line item credits get applied first to the line items
        and invoice credits get applied to the remaining balance.
        """
        user_rate_credit_by_account = CreditLine.add_credit(
            self.monthly_user_fee, account=self.account,
            feature_type=self.user_rate.feature.feature_type,
        )
        self.assertEqual(CreditAdjustment.objects.filter(
            credit_line=user_rate_credit_by_account).count(), 1
        )

        user_rate_credit_by_subscription = CreditLine.add_credit(
            self.monthly_user_fee,
            feature_type=self.user_rate.feature.feature_type,
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

    def _generate_subscription_and_account_invoice_credits(self, monthly_fee, subscription, account):
        subscription_credit = CreditLine.add_credit(
            monthly_fee, subscription=subscription,
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=subscription_credit).count(), 1)

        account_credit = CreditLine.add_credit(
            monthly_fee, account=account
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=account_credit).count(), 1)
        return subscription_credit, account_credit

    def _test_final_invoice_balance(self):
        for month_num in range(2, 5):
            invoice_date = utils.months_from_date(self.subscription.date_start, month_num)
            tasks.calculate_users_in_all_domains(invoice_date)
            tasks.generate_invoices_based_on_date(invoice_date)
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
        product_credit = CreditLine.add_credit(
            self.product_rate.monthly_fee, account=self.account,
            is_product=True,
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=product_credit).count(), 1)
        CreditLine.add_credit(
            self.product_rate.monthly_fee, account=self.account,
            is_product=True,
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=product_credit).count(), 2)
        current_product_credit = CreditLine.objects.get(id=product_credit.id)
        self.assertEqual(current_product_credit.balance, self.product_rate.monthly_fee * 2)

        subscription_credit = CreditLine.add_credit(
            self.monthly_user_fee, subscription=self.subscription
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=subscription_credit).count(), 1)
        CreditLine.add_credit(
            self.monthly_user_fee, subscription=self.subscription,
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=subscription_credit).count(), 2)
        current_subscription_credit = CreditLine.objects.get(id=subscription_credit.id)
        self.assertEqual(current_subscription_credit.balance, self.monthly_user_fee * 2)

        account_credit = CreditLine.add_credit(
            self.product_rate.monthly_fee, account=self.account
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=account_credit).count(), 1)
        CreditLine.add_credit(
            self.monthly_user_fee, account=self.account
        )
        self.assertEqual(CreditAdjustment.objects.filter(credit_line=account_credit).count(), 2)
        current_account_credit = CreditLine.objects.get(id=account_credit.id)
        self.assertEqual(current_account_credit.balance, self.product_rate.monthly_fee + self.monthly_user_fee)


class TestDeactivatedCredits(BaseInvoiceTestCase):

    def add_account_credit(self, amount):
        account_credit = CreditLine.add_credit(amount, account=self.account)
        self.assertEqual(CreditLine.get_credits_for_account(self.account).count(), 1)
        self.assertEqual(account_credit, CreditLine.get_credits_for_account(self.account).first())
        return account_credit

    def add_product_credit(self, amount):
        product_credit = CreditLine.add_credit(amount, subscription=self.subscription, is_product=True)
        product_credits = CreditLine.get_credits_by_subscription_and_features(
            subscription=self.subscription, is_product=True
        )
        self.assertEqual(1, product_credits.count())
        self.assertEqual(product_credit, product_credits.first())
        return product_credit

    def add_sms_credit(self, amount):
        sms_credit = CreditLine.add_credit(amount, subscription=self.subscription, feature_type=FeatureType.SMS)
        sms_credits = CreditLine.get_credits_by_subscription_and_features(
            subscription=self.subscription, feature_type=FeatureType.SMS
        )
        self.assertEqual(1, sms_credits.count())
        self.assertEqual(sms_credit, sms_credits.first())
        return sms_credit

    def add_user_credit(self, amount):
        user_credit = CreditLine.add_credit(amount, subscription=self.subscription, feature_type=FeatureType.USER)
        user_credits = CreditLine.get_credits_by_subscription_and_features(
            subscription=self.subscription, feature_type=FeatureType.USER
        )
        self.assertEqual(1, user_credits.count())
        self.assertEqual(user_credit, user_credits.first())
        return user_credit

    def test_get_credits_for_account_only_returns_active_credit(self):
        account_credit = self.add_account_credit(100.00)

        # Deactivate credit line
        account_credit.is_active = False
        account_credit.save()

        # Check that get_credits_for_account does not return deactivated credit line
        self.assertEqual(CreditLine.get_credits_for_account(self.account).count(), 0)

    def test_get_credits_by_subscription_and_features_only_returns_active_credits(self):
        # Add credits to subscription
        product_credit = self.add_product_credit(100.00)
        sms_credit = self.add_sms_credit(200.00)
        user_credit = self.add_user_credit(300.00)

        # Deactivate one credit
        sms_credit.is_active = False
        sms_credit.save()

        # Check that get_credits_by_subscription_and_features only returns active credit lines
        product_credits = CreditLine.get_credits_by_subscription_and_features(
            subscription=self.subscription, is_product=True
        )
        self.assertEqual(1, product_credits.count())
        self.assertEqual(product_credit, product_credits.first())

        user_credits = CreditLine.get_credits_by_subscription_and_features(
            subscription=self.subscription, feature_type=FeatureType.USER
        )
        self.assertEqual(1, user_credits.count())
        self.assertEqual(user_credit, user_credits.first())

        sms_credits = CreditLine.get_credits_by_subscription_and_features(
            subscription=self.subscription, feature_type=FeatureType.SMS
        )
        self.assertEqual(0, sms_credits.count())

    def test_get_non_general_credits_by_subscription_only_returns_active_credits(self):
        # Add credits to subscription
        product_credit = self.add_product_credit(100.00)
        sms_credit = self.add_sms_credit(200.00)
        user_credit = self.add_user_credit(300.00)

        non_general_credits = CreditLine.get_non_general_credits_by_subscription(subscription=self.subscription)
        self.assertEqual(3, non_general_credits.count())
        self.assertIn(product_credit, non_general_credits)
        self.assertIn(sms_credit, non_general_credits)
        self.assertIn(user_credit, non_general_credits)

        # Deactivate one credit
        sms_credit.is_active = False
        sms_credit.save()

        non_general_credits = CreditLine.get_non_general_credits_by_subscription(subscription=self.subscription)
        self.assertEqual(2, non_general_credits.count())
        self.assertIn(product_credit, non_general_credits)
        self.assertNotIn(sms_credit, non_general_credits)
        self.assertIn(user_credit, non_general_credits)


class TestCreditTransfers(BaseAccountingTest):

    @classmethod
    def setUpClass(cls):
        super(TestCreditTransfers, cls).setUpClass()
        cls.product_credit_amt = Decimal('500.00')
        cls.feature_credit_amt = Decimal('200.00')
        cls.subscription_credit_amt = Decimal('600.00')
        cls.domain = generator.arbitrary_domain()
        cls.account = BillingAccount.get_or_create_account_by_domain(
            cls.domain, created_by="biyeun@dimagi.com",
        )[0]
        cls.web_user_name = generator.create_arbitrary_web_user_name()
        cls.other_account = generator.billing_account(cls.web_user_name, cls.web_user_name)

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(TestCreditTransfers, cls).tearDownClass()

    def _ensure_transfer(self, original_credits):
        transferred_credits = []
        for credit_line in original_credits:
            refreshed_credit = CreditLine.objects.get(pk=credit_line.pk)
            self.assertFalse(refreshed_credit.is_active)
            self.assertEqual(credit_line.feature_type, refreshed_credit.feature_type)
            self.assertEqual(credit_line.is_product, refreshed_credit.is_product)
            self.assertEqual(credit_line.account, refreshed_credit.account)
            self.assertEqual(refreshed_credit.balance, Decimal('0.0000'))
            adjustments = refreshed_credit.creditadjustment_set.filter(
                reason=CreditAdjustmentReason.TRANSFER
            )
            self.assertTrue(adjustments.exists())
            transfer_adjustment = adjustments.latest('date_created')
            transferred_credits.append(transfer_adjustment.related_credit)
            self.assertEqual(
                transfer_adjustment.related_credit.balance,
                credit_line.balance
            )
        return transferred_credits

    def test_transfers(self):
        advanced_plan = DefaultProductPlan.get_default_plan_version(
            edition=SoftwarePlanEdition.ADVANCED
        )
        standard_plan = DefaultProductPlan.get_default_plan_version(
            edition=SoftwarePlanEdition.STANDARD
        )
        first_sub = Subscription.new_domain_subscription(
            self.account, self.domain.name, advanced_plan,
            date_start=datetime.date.today() - relativedelta(days=1),
        )

        product_credit = CreditLine.add_credit(
            self.product_credit_amt, subscription=first_sub,
            is_product=True,
        )
        feature_credit = CreditLine.add_credit(
            self.feature_credit_amt, subscription=first_sub,
            feature_type=FeatureType.USER,
        )
        subscription_credit = CreditLine.add_credit(
            self.subscription_credit_amt, subscription=first_sub,
        )
        original_credits = [
            product_credit, feature_credit, subscription_credit,
        ]

        second_sub = first_sub.change_plan(standard_plan)

        second_credits = self._ensure_transfer(original_credits)
        for credit_line in second_credits:
            self.assertEqual(credit_line.subscription.pk, second_sub.pk)

        second_sub.date_end = datetime.date.today() + datetime.timedelta(days=5)
        second_sub.save()
        third_sub = second_sub.renew_subscription()
        deactivate_subscriptions(second_sub.date_end)
        third_sub = Subscription.visible_objects.get(id=third_sub.id)

        third_credits = self._ensure_transfer(second_credits)
        for credit_line in third_credits:
            self.assertEqual(credit_line.subscription.pk, third_sub.pk)

        third_sub.date_end = third_sub.date_start + relativedelta(days=1)
        third_sub.save()
        Subscription.new_domain_subscription(
            self.other_account, self.domain, DefaultProductPlan.get_default_plan_version(),
            date_start=third_sub.date_end,
        )
        deactivate_subscriptions(third_sub.date_end)

        account_credits = self._ensure_transfer(third_credits)
        for credit_line in account_credits:
            self.assertIsNone(credit_line.subscription)
            self.assertEqual(credit_line.account.pk, self.account.pk)


class TestUserSubscriptionChangeTransfers(BaseAccountingTest):

    @classmethod
    def setUpClass(cls):
        super(TestUserSubscriptionChangeTransfers, cls).setUpClass()

        generator.bootstrap_test_software_plan_versions()
        generator.init_default_currency()

        cls.billing_contact = generator.create_arbitrary_web_user_name()
        cls.domain = generator.arbitrary_domain()
        cls.account = BillingAccount.get_or_create_account_by_domain(
            cls.domain, created_by=cls.billing_contact,
        )[0]
        generator.arbitrary_contact_info(cls.account, cls.billing_contact)

    def tearDown(self):
        for user in self.domain.all_users():
            user.delete(self.domain.name, deleted_by=None)
        super(BaseAccountingTest, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        utils.clear_plan_version_cache()
        super(TestUserSubscriptionChangeTransfers, cls).tearDownClass()

    def _get_credit_total(self, subscription):
        credit_lines = CreditLine.get_credits_by_subscription_and_features(
            subscription
        )
        return sum([c.balance for c in credit_lines])

    def test_subscription_credits_transfer_in_invoice(self):
        standard_plan = DefaultProductPlan.get_default_plan_version(
            edition=SoftwarePlanEdition.STANDARD
        )
        pro_plan = DefaultProductPlan.get_default_plan_version(
            edition=SoftwarePlanEdition.PRO
        )

        first_sub = Subscription.new_domain_subscription(
            self.account, self.domain.name, standard_plan,
            date_start=datetime.date(2019, 9, 1),
        )
        credit_amount = Decimal('5000.00')
        CreditLine.add_credit(
            credit_amount, subscription=first_sub,
        )

        # this is the key step where the expected transfer happens
        second_sub = first_sub.change_plan(pro_plan)

        first_sub = Subscription.visible_objects.get(id=first_sub.id)
        first_sub.date_end = datetime.date(2019, 9, 10)
        first_sub.save()
        second_sub.date_start = first_sub.date_end
        second_sub.save()

        invoice_date = utils.months_from_date(first_sub.date_start, 1)
        user_record_date = invoice_date - relativedelta(days=1)
        DomainUserHistory.objects.create(
            domain=self.domain,
            num_users=0,
            record_date=user_record_date
        )
        tasks.generate_invoices_based_on_date(utils.months_from_date(first_sub.date_start, 1))

        self.assertEqual(first_sub.invoice_set.count(), 1)
        self.assertEqual(second_sub.invoice_set.count(), 1)

        first_invoice = first_sub.invoice_set.first()
        second_invoice = second_sub.invoice_set.first()

        self.assertEqual(first_invoice.balance, Decimal('0.0000'))
        self.assertEqual(second_invoice.balance, Decimal('0.0000'))
        self.assertEqual(self._get_credit_total(second_sub), Decimal('4490.0000'))
