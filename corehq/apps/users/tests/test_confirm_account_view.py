from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.util.test_utils import flag_enabled


class TestMobileWorkerConfirmAccountView(TestCase):
    domain = 'mobile-worker-confirm-account'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super().tearDownClass()

    def setUp(self):
        self.user = CommCareUser.create(
            self.domain,
            'mw1',
            's3cr4t',
            None,
            None,
            email='mw1@example.com',
            is_account_confirmed=False,
        )
        self.url = reverse('commcare_user_confirm_account', args=[self.domain, self.user.get_id])

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)

    @flag_enabled('TWO_STAGE_USER_PROVISIONING')
    def test_expected_workflow(self):
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Confirm your account')

    def test_feature_flag_not_enabled(self):
        response = self.client.get(self.url)
        self.assertEqual(404, response.status_code)

    @flag_enabled('TWO_STAGE_USER_PROVISIONING')
    def test_user_id_not_found(self):
        response = self.client.get(reverse('commcare_user_confirm_account', args=[self.domain, 'missing-id']))
        self.assertEqual(404, response.status_code)

    @flag_enabled('TWO_STAGE_USER_PROVISIONING')
    def test_user_domain_mismatch(self):
        response = self.client.get(reverse('commcare_user_confirm_account',
                                           args=['wrong-domain', self.user.get_id]))
        self.assertEqual(404, response.status_code)

    @flag_enabled('TWO_STAGE_USER_PROVISIONING')
    def test_account_active(self):
        self.user.is_account_confirmed = True
        self.user.is_active = True
        self.user.save()
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Your account is already confirmed')

    @flag_enabled('TWO_STAGE_USER_PROVISIONING')
    def test_account_inactive_but_confirmed(self):
        self.user.is_account_confirmed = True
        self.user.is_active = False
        self.user.save()
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'your account has been deactivated')
