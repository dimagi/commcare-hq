import json

from django.test.testcases import TestCase
from django.urls import reverse

from corehq.apps.accounting.models import (
    BillingAccount,
    DefaultProductPlan,
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import HQApiKey, WebUser
from corehq.apps.zapier.views import ZapierCreateCase, ZapierUpdateCase
from corehq.form_processor.models import CommCareCase
from corehq.form_processor.tests.utils import FormProcessorTestUtils


class TestZapierCreateCaseAction(TestCase):
    """
    NOTE: This test case tests APIs to create/update cases from Zapier that are not currently in use / live.
    """

    @classmethod
    def setUpClass(cls):
        super(TestZapierCreateCaseAction, cls).setUpClass()
        cls.domain_object = Domain.get_or_create_with_name('fruit', is_active=True)
        cls.domain = cls.domain_object.name
        account = BillingAccount.get_or_create_account_by_domain(cls.domain, created_by="automated-test")[0]
        plan = DefaultProductPlan.get_default_plan_version(edition=SoftwarePlanEdition.STANDARD)
        subscription = Subscription.new_domain_subscription(account, cls.domain, plan)
        subscription.is_active = True
        subscription.save()
        cls.query_string = "?domain=fruit&case_type=watermelon&owner_id=test_user&user=test"
        cls.data = {'case_name': 'test1', 'price': '11'}
        cls.user = WebUser.create(cls.domain, 'test', '******', None, None)
        api_key_object, _ = HQApiKey.objects.get_or_create(user=cls.user.get_django_user())
        cls.api_key = api_key_object.plaintext_key

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        cls.domain_object.delete()
        FormProcessorTestUtils.delete_all_cases()
        super(TestZapierCreateCaseAction, cls).tearDownClass()

    def test_create_case(self):
        response = self.client.post(reverse(ZapierCreateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(self.data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 200)

        case_id = CommCareCase.objects.get_case_ids_in_domain(self.domain)
        case = CommCareCase.objects.get_case(case_id[0], self.domain)
        self.assertEqual('test1', case.get_case_property('name'))
        self.assertEqual('11', case.get_case_property('price'))
        self.assertEqual('watermelon', case.get_case_property('type'))

    def test_update_case(self):
        response = self.client.post(reverse(ZapierCreateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(self.data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 200)
        case_id = CommCareCase.objects.get_case_ids_in_domain(self.domain)
        case = CommCareCase.objects.get_case(case_id[0], self.domain)
        self.assertEqual('11', case.get_case_property('price'))

        data = {'case_name': 'test1', 'price': '15', 'case_id': case_id[0]}
        response = self.client.post(reverse(ZapierUpdateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 200)
        case = CommCareCase.objects.get_case(case_id[0], self.domain)
        self.assertEqual('15', case.get_case_property('price'))

    def test_update_case_does_not_exist(self):
        data = {'case_name': 'test1', 'price': '15', 'case_id': 'fake_id'}
        response = self.client.post(reverse(ZapierUpdateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 404)

    def test_update_case_wrong_domain(self):
        response = self.client.post(reverse(ZapierCreateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(self.data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 200)
        case_id = CommCareCase.objects.get_case_ids_in_domain(self.domain)

        data = {'case_name': 'test1', 'price': '15', 'case_id': case_id[0]}
        query_string = "?domain=me&case_type=watermelon&user_id=test_user&user=test"
        response = self.client.post(reverse(ZapierUpdateCase.urlname,
                                            kwargs={'domain': self.domain}) + query_string,
                               data=json.dumps(data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 403)

    def test_update_case_wrong_type(self):
        response = self.client.post(reverse(ZapierCreateCase.urlname,
                                            kwargs={'domain': self.domain}) + self.query_string,
                               data=json.dumps(self.data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 200)
        case_id = CommCareCase.objects.get_case_ids_in_domain(self.domain)

        data = {'case_name': 'test1', 'price': '15', 'case_id': case_id[0]}
        query_string = "?domain=fruit&case_type=orange&user_id=test_user&user=test"
        response = self.client.post(reverse(ZapierUpdateCase.urlname,
                                            kwargs={'domain': self.domain}) + query_string,
                               data=json.dumps(data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 400)

    def test_user_does_not_have_access(self):
        fake_domain = Domain.get_or_create_with_name('fake', is_active=True)
        WebUser.create('fake', 'faker2', '******', None, None)
        self.addCleanup(fake_domain.delete)
        query_string = "?domain=fruit&case_type=fake&user_id=test_user&user=faker2&owner_id=test_user"
        response = self.client.post(reverse(ZapierCreateCase.urlname,
                                            kwargs={'domain': self.domain}) + query_string,
                               data=json.dumps(self.data),
                               content_type='application/json',
                               HTTP_AUTHORIZATION='ApiKey test:{}'.format(self.api_key))

        self.assertEqual(response.status_code, 403)
