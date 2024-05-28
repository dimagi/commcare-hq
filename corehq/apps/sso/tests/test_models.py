from unittest.mock import patch
from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.tests import generator
from django.test import TestCase


class IdentityProviderTests(TestCase):
    @patch('corehq.apps.sso.tasks.update_sso_user_api_key_expiration_dates')
    def test_more_restrictive_api_key_expiration_date_updates_api_key_expirations(self, mock_task):
        idp = self._create_identity_provider(max_days_until_user_api_key_expiration=None)

        idp.max_days_until_user_api_key_expiration = 30
        idp.save()

        mock_task.delay.assert_called()

    @patch('corehq.apps.sso.tasks.update_sso_user_api_key_expiration_dates')
    def test_unchanged_api_key_expiration_does_not_call_task(self, mock_task):
        idp = self._create_identity_provider(max_days_until_user_api_key_expiration=30)

        idp.max_days_until_user_api_key_expiration = 30
        idp.save()

        mock_task.delay.assert_not_called()

    @patch('corehq.apps.sso.tasks.update_sso_user_api_key_expiration_dates')
    def test_less_restrictive_api_key_expiration_date_does_not_call_task(self, mock_task):
        idp = self._create_identity_provider(max_days_until_user_api_key_expiration=30)

        idp.max_days_until_user_api_key_expiration = 60
        idp.save()

        mock_task.delay.assert_not_called()

    @patch('corehq.apps.sso.tasks.update_sso_user_api_key_expiration_dates')
    def test_removing_max_api_expiration_does_not_call_task(self, mock_task):
        idp = self._create_identity_provider(max_days_until_user_api_key_expiration=30)

        idp.max_days_until_user_api_key_expiration = None
        idp.save()

        mock_task.delay.assert_not_called()

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.billing_account = generator.get_billing_account_for_idp()

    def _create_identity_provider(self, max_days_until_user_api_key_expiration=None):
        return IdentityProvider.objects.create(
            owner=self.billing_account,
            name='Test IDP',
            slug='testidp',
            created_by='admin@dimagi.com',
            last_modified_by='admin@dimagi.com',
            max_days_until_user_api_key_expiration=max_days_until_user_api_key_expiration,
        )
