import datetime

from django.test import TestCase

from corehq.apps.accounting import tasks
from corehq.apps.accounting.models import (
    BillingAccountWebUserHistory,
    DomainUserHistory,
    FormSubmittingMobileWorkerHistory,
    SoftwarePlanEdition,
)
from corehq.apps.accounting.tests import generator
from corehq.apps.accounting.tests.test_invoicing import BaseInvoiceTestCase
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.es.forms import form_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.form_processor.utils.xform import TestFormMetadata
from corehq.util.test_utils import make_es_ready_form


class TestDomainUserHistory(BaseInvoiceTestCase):

    @classmethod
    def setUpClass(cls):
        delete_all_domains()
        super().setUpClass()

    def setUp(self):
        super(TestDomainUserHistory, self).setUp()
        self.num_users = 2
        generator.arbitrary_commcare_users_for_domain(self.domain.name, self.num_users)
        self.today = datetime.date.today()
        self.record_date = self.today - datetime.timedelta(days=1)

    def tearDown(self):
        for user in self.domain.all_users():
            user.delete(self.domain.name, deleted_by=None)
        super(TestDomainUserHistory, self).tearDown()

    def test_domain_user_history(self):
        domain_user_history = DomainUserHistory.objects.create(domain=self.domain.name,
                                                       num_users=self.num_users,
                                                       record_date=self.record_date)
        self.assertEqual(domain_user_history.domain, self.domain.name)
        self.assertEqual(domain_user_history.num_users, self.num_users)
        # DomainUserHistory calculates number of users and assigns to the previous month for statements
        self.assertEqual(domain_user_history.record_date, self.record_date)

    def test_calculate_users_in_all_domains(self):
        tasks.calculate_users_in_all_domains()
        self.assertEqual(DomainUserHistory.objects.count(), 1)
        domain_user_history = DomainUserHistory.objects.first()
        self.assertEqual(domain_user_history.domain, self.domain.name)
        self.assertEqual(domain_user_history.num_users, self.num_users)
        self.assertEqual(domain_user_history.record_date, self.record_date)


@es_test(requires=[form_adapter], setup_class=True)
class TestFormSubmittingMobileWorkerHistory(BaseInvoiceTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        num_workers = 5
        generator.arbitrary_commcare_users_for_domain(cls.domain.name, num_workers)

        cls.num_form_submitting_workers = 3
        cls.one_day_ago = datetime.date.today() - datetime.timedelta(days=1)
        one_week_ago_dt = datetime.datetime.combine(
            cls.one_day_ago - datetime.timedelta(days=6), datetime.time()
        )
        for user in cls.domain.all_users()[:cls.num_form_submitting_workers]:
            cls._submit_form(user, one_week_ago_dt)

    @classmethod
    def _submit_form(cls, user, received_on):
        form_pair = make_es_ready_form(
            TestFormMetadata(
                domain=cls.domain.name,
                user_id=user.user_id,
                received_on=received_on
            )
        )
        form_adapter.index(form_pair.json_form, refresh=True)

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        delete_all_domains()
        return super().tearDownClass()

    def test_form_submitting_mobile_worker_history(self):
        worker_history = FormSubmittingMobileWorkerHistory.objects.create(
            domain=self.domain.name,
            num_users=self.num_form_submitting_workers,
            record_date=self.one_day_ago
        )
        self.assertEqual(worker_history.domain, self.domain.name)
        self.assertEqual(worker_history.num_users, self.num_form_submitting_workers)
        self.assertEqual(worker_history.record_date, self.one_day_ago)

    def test_calculate_form_submitting_mobile_workers_in_all_domains(self):
        tasks.calculate_form_submitting_mobile_workers_in_all_domains()
        self.assertEqual(FormSubmittingMobileWorkerHistory.objects.count(), 1)

        worker_history = FormSubmittingMobileWorkerHistory.objects.first()
        self.assertEqual(worker_history.domain, self.domain.name)
        self.assertEqual(worker_history.num_users, self.num_form_submitting_workers)
        self.assertEqual(worker_history.record_date, self.one_day_ago)


class TestBillingAccountWebUserHistory(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.billing_contact_enterprise = generator.create_arbitrary_web_user_name()
        cls.billing_contact_standard = generator.create_arbitrary_web_user_name()

        cls.dimagi_user = generator.create_arbitrary_web_user_name(is_dimagi=True)
        cls.currency = generator.init_default_currency()
        cls.account_enterprise = generator.billing_account(
            cls.dimagi_user, cls.billing_contact_enterprise, is_customer_account=True)
        cls.account_standard = generator.billing_account(
            cls.dimagi_user, cls.billing_contact_standard, is_customer_account=True
        )

        cls.domain_1 = generator.arbitrary_domain()
        cls.domain_2 = generator.arbitrary_domain()
        cls.domain_3 = generator.arbitrary_domain()

        subscription_start_date = datetime.date(2022, 3, 1)
        enterprise_plan = generator.subscribable_plan_version(edition=SoftwarePlanEdition.ENTERPRISE)

        cls.domain_1_enterprise_subscription = generator.generate_domain_subscription(
            cls.account_enterprise,
            cls.domain_1,
            date_start=subscription_start_date,
            date_end=None,
            plan_version=enterprise_plan,
            is_active=True,
        )
        cls.domain_2_enterprise_subscription = generator.generate_domain_subscription(
            cls.account_enterprise,
            cls.domain_2,
            date_start=subscription_start_date,
            date_end=None,
            plan_version=enterprise_plan,
            is_active=True,
        )

        cls.standard_subscription = generator.generate_domain_subscription(
            cls.account_standard,
            cls.domain_3,
            date_start=subscription_start_date,
            date_end=None,
            is_active=True,
        )

        generator.arbitrary_webusers_for_domain(cls.domain_1.name, 2)
        generator.arbitrary_webusers_for_domain(cls.domain_2.name, 2)
        generator.arbitrary_webusers_for_domain(cls.domain_3.name, 2)

    def test_calculate_web_users_for_enterprise_account(self):
        tasks.calculate_web_users_in_all_billing_accounts()
        enterprise_users = BillingAccountWebUserHistory.objects.get(
            billing_account=self.account_enterprise
        ).num_users

        # Should have users from both domain_1 and domain_2
        self.assertEqual(enterprise_users, 4)

    def test_calculate_web_users_for_standard_account(self):
        tasks.calculate_web_users_in_all_billing_accounts()
        standard_users = BillingAccountWebUserHistory.objects.get(billing_account=self.account_standard).num_users

        # Should only have users from both domain_2
        self.assertEqual(standard_users, 2)

    def test_mobile_workers_are_not_counted(self):
        generator.arbitrary_commcare_users_for_domain(self.domain_3.name, 3)
        tasks.calculate_web_users_in_all_billing_accounts()
        standard_users = BillingAccountWebUserHistory.objects.get(billing_account=self.account_standard).num_users

        # Should only have users from both domain_2
        self.assertEqual(standard_users, 2)

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        delete_all_domains()
        return super().tearDownClass()
