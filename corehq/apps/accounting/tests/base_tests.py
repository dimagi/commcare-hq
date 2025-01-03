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
        super(BaseInvoiceTestCase, cls).setUpClass()

        if cls.is_using_test_plans:
            generator.bootstrap_test_software_plan_versions()

        cls.billing_contact = generator.create_arbitrary_web_user_name()
        cls.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        cls.currency = generator.init_default_currency()
        cls.account = generator.billing_account(
            cls.dimagi_user, cls.billing_contact)
        cls.domain = generator.arbitrary_domain()

        cls.subscription_length = 15  # months
        cls.subscription_start_date = datetime.date(2016, 2, 23)
        cls.subscription_is_active = False
        if cls.is_testing_web_user_feature:
            # make sure the subscription is still active when we count web users
            cls.subscription_is_active = True
        cls.subscription_end_date = cls.subscription_start_date + relativedelta(months=cls.subscription_length)
        cls.subscription = generator.generate_domain_subscription(
            cls.account,
            cls.domain,
            date_start=cls.subscription_start_date,
            date_end=cls.subscription_end_date,
            is_active=cls.subscription_is_active
        )

    def tearDown(self):
        for user in self.domain.all_users():
            user.delete(self.domain.name, deleted_by=None)
        super(BaseAccountingTest, self).tearDown()

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()

        if cls.is_using_test_plans:
            utils.clear_plan_version_cache()

        super(BaseInvoiceTestCase, cls).tearDownClass()

    def create_invoices(self, date, calculate_users=True, calculate_web_users=False):
        if calculate_users:
            calculate_users_in_all_domains(date)

        if calculate_web_users:
            calculate_web_users_in_all_billing_accounts(date)

        generate_invoices_based_on_date(date)
