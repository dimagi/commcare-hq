import datetime

from django_prbac.models import Role

from corehq.apps.accounting.models import (
    SoftwarePlan,
    SoftwarePlanEdition,
    SoftwarePlanVisibility,
    SoftwarePlanVersion,
    SoftwareProductRate,
    Subscription,
    SubscriptionType,
    FundingSource,
    ProBonoStatus,
)
from corehq.apps.accounting.tests.base_tests import BaseAccountingTest
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.utils.software_plans import (
    upgrade_subscriptions_to_latest_plan_version,
)
from unittest.mock import patch
from django.core.management import call_command


class TestUpgradeSoftwarePlanToLatestVersion(BaseAccountingTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain1, subscriber1 = generator.arbitrary_domain_and_subscriber()
        cls.domain2, subscriber2 = generator.arbitrary_domain_and_subscriber()
        cls.admin_web_user = generator.create_arbitrary_web_user_name()

        account = generator.billing_account(cls.admin_web_user, cls.admin_web_user)
        account.is_customer_billing_account = True
        account.save()

        enterprise_plan = SoftwarePlan.objects.create(
            name="Helping Earth INGO Enterprise Plan",
            description="Enterprise plan for Helping Earth",
            edition=SoftwarePlanEdition.ENTERPRISE,
            visibility=SoftwarePlanVisibility.INTERNAL,
            is_customer_software_plan=True,
        )

        first_product_rate = SoftwareProductRate.objects.create(
            monthly_fee=3000,
            name="HQ Enterprise"
        )
        cls.first_version = SoftwarePlanVersion.objects.create(
            plan=enterprise_plan,
            role=Role.objects.first(),
            product_rate=first_product_rate
        )
        cls.first_version.save()

        today = datetime.date.today()
        two_months_ago = today - datetime.timedelta(days=60)
        next_month = today + datetime.timedelta(days=30)

        subscription1 = Subscription(
            account=account,
            plan_version=cls.first_version,
            subscriber=subscriber1,
            date_start=two_months_ago,
            date_end=None,
            service_type=SubscriptionType.IMPLEMENTATION,
        )
        subscription1.is_active = True
        subscription1.save()

        subscription2 = Subscription(
            account=account,
            plan_version=cls.first_version,
            subscriber=subscriber2,
            date_start=two_months_ago,
            date_end=next_month,
            service_type=SubscriptionType.IMPLEMENTATION,
        )
        subscription2.is_active = True
        subscription2.salesforce_contract_id = "salesforce-id-test"
        subscription2.do_not_invoice = True
        subscription2.no_invoice_reason = "test no invoice"
        subscription2.do_not_email_invoice = True
        subscription2.do_not_email_reminder = True
        subscription2.auto_generate_credits = True
        subscription2.skip_invoicing_if_no_feature_charges = True
        subscription2.service_type = SubscriptionType.SANDBOX
        subscription2.pro_bono_status = ProBonoStatus.DISCOUNTED
        subscription2.funding_source = FundingSource.EXTERNAL
        subscription2.skip_auto_downgrade = True
        subscription2.skip_auto_downgrade_reason = "test skip auto downgrade"
        subscription2.save()

        new_product_rate = SoftwareProductRate.objects.create(
            monthly_fee=5000,
            name="HQ Enterprise"
        )
        cls.newest_version = SoftwarePlanVersion.objects.create(
            plan=enterprise_plan,
            role=Role.objects.first(),
            product_rate=new_product_rate
        )
        cls.newest_version.save()

    def test_that_upgrade_occurs(self):
        old_subscription1 = Subscription.get_active_subscription_by_domain(self.domain1)
        self.assertEqual(old_subscription1.plan_version, self.first_version)
        self.assertEqual(old_subscription1.salesforce_contract_id, '')
        self.assertFalse(old_subscription1.do_not_invoice)
        self.assertEqual(old_subscription1.no_invoice_reason, '')
        self.assertFalse(old_subscription1.do_not_email_invoice)
        self.assertFalse(old_subscription1.do_not_email_reminder)
        self.assertFalse(old_subscription1.auto_generate_credits)
        self.assertFalse(old_subscription1.skip_invoicing_if_no_feature_charges)
        self.assertEqual(old_subscription1.service_type, SubscriptionType.IMPLEMENTATION)
        self.assertEqual(old_subscription1.pro_bono_status, ProBonoStatus.NO)
        self.assertEqual(old_subscription1.funding_source, FundingSource.CLIENT)
        self.assertFalse(old_subscription1.skip_auto_downgrade)
        self.assertEqual(old_subscription1.skip_auto_downgrade_reason, '')

        old_subscription2 = Subscription.get_active_subscription_by_domain(self.domain2)
        self.assertEqual(old_subscription2.plan_version, self.first_version)
        self.assertEqual(old_subscription2.salesforce_contract_id, "salesforce-id-test")
        self.assertTrue(old_subscription2.do_not_invoice)
        self.assertEqual(old_subscription2.no_invoice_reason, "test no invoice")
        self.assertTrue(old_subscription2.do_not_email_invoice)
        self.assertTrue(old_subscription2.do_not_email_reminder)
        self.assertTrue(old_subscription2.auto_generate_credits)
        self.assertTrue(old_subscription2.skip_invoicing_if_no_feature_charges)
        self.assertEqual(old_subscription2.service_type, SubscriptionType.SANDBOX)
        self.assertEqual(old_subscription2.pro_bono_status, ProBonoStatus.DISCOUNTED)
        self.assertEqual(old_subscription2.funding_source, FundingSource.EXTERNAL)
        self.assertTrue(old_subscription2.skip_auto_downgrade)
        self.assertEqual(old_subscription2.skip_auto_downgrade_reason, "test skip auto downgrade")

        upgrade_subscriptions_to_latest_plan_version(
            self.first_version,
            self.admin_web_user,
            upgrade_note="test upgrading to latest version"
        )

        new_subscription1 = Subscription.get_active_subscription_by_domain(self.domain1)
        self.assertEqual(new_subscription1.plan_version, self.newest_version)
        self.assertEqual(new_subscription1.salesforce_contract_id, '')
        self.assertFalse(new_subscription1.do_not_invoice)
        self.assertEqual(new_subscription1.no_invoice_reason, '')
        self.assertFalse(new_subscription1.do_not_email_invoice)
        self.assertFalse(new_subscription1.do_not_email_reminder)
        self.assertFalse(new_subscription1.auto_generate_credits)
        self.assertFalse(new_subscription1.skip_invoicing_if_no_feature_charges)
        self.assertEqual(new_subscription1.service_type, SubscriptionType.IMPLEMENTATION)
        self.assertEqual(new_subscription1.pro_bono_status, ProBonoStatus.NO)
        self.assertEqual(new_subscription1.funding_source, FundingSource.CLIENT)
        self.assertFalse(new_subscription1.skip_auto_downgrade)
        self.assertEqual(new_subscription1.skip_auto_downgrade_reason, '')

        new_subscription2 = Subscription.get_active_subscription_by_domain(self.domain2)
        self.assertEqual(new_subscription2.plan_version, self.newest_version)
        self.assertEqual(new_subscription2.salesforce_contract_id, "salesforce-id-test")
        self.assertTrue(new_subscription2.do_not_invoice)
        self.assertEqual(new_subscription2.no_invoice_reason, "test no invoice")
        self.assertTrue(new_subscription2.do_not_email_invoice)
        self.assertTrue(new_subscription2.do_not_email_reminder)
        self.assertTrue(new_subscription2.auto_generate_credits)
        self.assertTrue(new_subscription2.skip_invoicing_if_no_feature_charges)
        self.assertEqual(new_subscription2.service_type, SubscriptionType.SANDBOX)
        self.assertEqual(new_subscription2.pro_bono_status, ProBonoStatus.DISCOUNTED)
        self.assertEqual(new_subscription2.funding_source, FundingSource.EXTERNAL)
        self.assertTrue(new_subscription2.skip_auto_downgrade)
        self.assertEqual(new_subscription2.skip_auto_downgrade_reason, "test skip auto downgrade")


class TestKeepSoftwarePlanConsistentManagementCommand(BaseAccountingTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain1, subscriber1 = generator.arbitrary_domain_and_subscriber()
        cls.domain2, subscriber2 = generator.arbitrary_domain_and_subscriber()
        cls.admin_web_user = generator.create_arbitrary_web_user_name()

        cls.account = generator.billing_account(cls.admin_web_user, cls.admin_web_user)
        cls.account.is_customer_billing_account = True
        cls.account.save()

        enterprise_plan = SoftwarePlan.objects.create(
            name="Helping Earth INGO Enterprise Plan",
            description="Enterprise plan for Helping Earth",
            edition=SoftwarePlanEdition.ENTERPRISE,
            visibility=SoftwarePlanVisibility.INTERNAL,
            is_customer_software_plan=True,
        )

        # Create first version of software plan
        first_product_rate = SoftwareProductRate.objects.create(
            monthly_fee=3000,
            name="HQ Enterprise"
        )
        cls.first_version = SoftwarePlanVersion.objects.create(
            plan=enterprise_plan,
            role=Role.objects.first(),
            product_rate=first_product_rate
        )
        cls.first_version.save()

        # Create second version of software plan
        new_product_rate = SoftwareProductRate.objects.create(
            monthly_fee=5000,
            name="HQ Enterprise"
        )
        cls.newest_version = SoftwarePlanVersion.objects.create(
            plan=enterprise_plan,
            role=Role.objects.first(),
            product_rate=new_product_rate
        )
        cls.newest_version.save()

        today = datetime.date.today()
        two_months_ago = today - datetime.timedelta(days=60)

        # Setup main billing domain and its subscription
        subscription1 = Subscription(
            account=cls.account,
            plan_version=cls.newest_version,
            subscriber=subscriber1,
            date_start=two_months_ago,
            date_end=None,
            service_type=SubscriptionType.IMPLEMENTATION,
            is_active=True
        )
        subscription1.save()

        subscription2 = Subscription(
            account=cls.account,
            plan_version=cls.first_version,
            subscriber=subscriber2,
            date_start=two_months_ago,
            date_end=None,
            service_type=SubscriptionType.IMPLEMENTATION,
            is_active=True,
            do_not_invoice=True,
            no_invoice_reason="test no invoice"
        )
        subscription2.save()

    def test_keep_software_plan_consistent_for_customer_billing_accounts(self):
        with patch('builtins.input', side_effect=[self.account.name, 'DONE']):
            old_subscription1 = Subscription.get_active_subscription_by_domain(self.domain1)
            self.assertEqual(old_subscription1.plan_version, self.newest_version)

            old_subscription2 = Subscription.get_active_subscription_by_domain(self.domain2)
            self.assertEqual(old_subscription2.plan_version, self.first_version)

            call_command('list_customer_billing_account_software_plan', update=True)

            new_subscription2 = Subscription.get_active_subscription_by_domain(self.domain2)
            self.assertEqual(new_subscription2.plan_version, self.newest_version)
