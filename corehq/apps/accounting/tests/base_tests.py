import datetime

from django.test import TestCase

from dateutil.relativedelta import relativedelta
from django_prbac.models import Role

from corehq.apps.accounting import utils
from corehq.apps.accounting.tasks import (
    calculate_users_in_all_domains,
    calculate_web_users_in_all_billing_accounts,
    generate_invoices_based_on_date,
)
from corehq.apps.accounting.tests import generator


class BaseAccountingTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseAccountingTest, cls).setUpClass()
        Role.get_cache().clear()


class BaseInvoiceTestCase(BaseAccountingTest):

    is_using_test_plans = False
    min_subscription_length = 3
    is_testing_web_user_feature = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if cls.is_using_test_plans:
            generator.bootstrap_test_software_plan_versions()

        cls.subscription_length = 15  # months
        cls.subscription_start_date = datetime.date(2016, 2, 23)
        cls.subscription_end_date = cls.subscription_start_date + relativedelta(months=cls.subscription_length)
        # make sure the subscription is still active when we count web users
        cls.subscription_is_active = cls.is_testing_web_user_feature
        cls.currency = generator.init_default_currency()

    def setUp(self):
        super().setUp()
        self.billing_contact = generator.create_arbitrary_web_user_name()
        self.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        self.account = generator.billing_account(self.dimagi_user, self.billing_contact)
        self.domain = generator.arbitrary_domain()
        self.subscription = generator.generate_domain_subscription(
            self.account,
            self.domain,
            date_start=self.subscription_start_date,
            date_end=self.subscription_end_date,
            is_active=self.subscription_is_active
        )
        self.addCleanup(self.cleanUp)

    def cleanUp(self):
        for user in self.domain.all_users():
            user.delete(self.domain.name, deleted_by=None)
        self.domain.delete()

    @classmethod
    def tearDownClass(cls):
        if cls.is_using_test_plans:
            utils.clear_plan_version_cache()

        super().tearDownClass()

    @staticmethod
    def create_invoices(date, calculate_users=True, calculate_web_users=False):
        if calculate_users:
            calculate_users_in_all_domains(date)

        if calculate_web_users:
            calculate_web_users_in_all_billing_accounts(date)

        generate_invoices_based_on_date(date)
