from django.test import TestCase
from django.urls import reverse
from unittest.mock import Mock, patch

from corehq import privileges

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.utils import encrypt_account_confirmation_info
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.views.mobile.users import CommCareUserConfirmAccountView
from corehq.util.test_utils import privilege_enabled


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
        encrypted_user_info = encrypt_account_confirmation_info(self.user)
        self.url = reverse('commcare_user_confirm_account', args=[self.domain, encrypted_user_info])

    def tearDown(self):
        self.user.delete(self.domain, deleted_by=None)

    @privilege_enabled(privileges.TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION)
    def test_expected_workflow(self):
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Confirm your account')

    def test_feature_flag_not_enabled(self):
        response = self.client.get(self.url)
        self.assertEqual(404, response.status_code)

    @privilege_enabled(privileges.TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION)
    def test_user_id_not_found(self):
        mock_commcare_user = Mock()
        mock_commcare_user.get_id = 'missing-id'
        encrypted_info = encrypt_account_confirmation_info(mock_commcare_user)

        response = self.client.get(reverse('commcare_user_confirm_account', args=[self.domain, encrypted_info]))
        self.assertEqual(404, response.status_code)

    @privilege_enabled(privileges.TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION)
    def test_user_domain_mismatch(self):
        response = self.client.get(reverse('commcare_user_confirm_account',
                                           args=['wrong-domain', self.user.get_id]))
        self.assertEqual(404, response.status_code)

    @privilege_enabled(privileges.TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION)
    def test_account_active(self):
        self.user.is_account_confirmed = True
        self.user.is_active = True
        self.user.save()
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Your account is already confirmed')

    @privilege_enabled(privileges.TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION)
    def test_account_inactive_but_confirmed(self):
        self.user.is_account_confirmed = True
        self.user.is_active = False
        self.user.save()
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'your account has been deactivated')

    @privilege_enabled(privileges.TWO_STAGE_MOBILE_WORKER_ACCOUNT_CREATION)
    @patch.object(CommCareUserConfirmAccountView, '_expiration_time_in_hours', new_callable=Mock(return_value=-1))
    def test_invite_expired_message(self, mock_expiration_time):
        response = self.client.get(self.url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Invitation link has expired")
