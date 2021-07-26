from unittest.mock import patch, MagicMock

from django.test import SimpleTestCase

from corehq.apps.linked_domain.util import is_domain_available_to_link, user_has_admin_access_in_all_domains


class TestIsDomainAvailableToLink(SimpleTestCase):

    @patch('corehq.apps.users.models.CouchUser')
    def test_none_upstream_domain_returns_false(self, mock_user):
        result = is_domain_available_to_link(None, 'domain', mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_none_candidate_domain_returns_false(self, mock_user):
        result = is_domain_available_to_link('domain', None, mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_none_upstream_and_none_candidate_domain_returns_false(self, mock_user):
        result = is_domain_available_to_link(None, None, mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_same_domain_returns_false(self, mock_user):
        result = is_domain_available_to_link('domain', 'domain', mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_domain_in_active_link_returns_false(self, mock_user):
        with patch('corehq.apps.linked_domain.util.is_domain_in_active_link') as mock_active_link:
            mock_active_link.return_value = True
            result = is_domain_available_to_link('upstream', 'downstream', mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_domain_not_in_active_link_without_admin_check_returns_true(self, mock_user):
        with patch('corehq.apps.linked_domain.util.is_domain_in_active_link') as mock_active_link:
            mock_active_link.return_value = False
            result = is_domain_available_to_link('upstream', 'downstream', mock_user, should_enforce_admin=False)
        self.assertTrue(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_user_without_admin_access_returns_false(self, mock_user):
        with patch('corehq.apps.linked_domain.util.is_domain_in_active_link') as mock_active_link,\
             patch('corehq.apps.linked_domain.util.user_has_admin_access_in_all_domains') as mock_admin:
            mock_active_link.return_value = False
            mock_admin.return_value = False
            result = is_domain_available_to_link('upstream', 'downstream', mock_user, should_enforce_admin=True)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_user_with_admin_access_returns_true(self, mock_user):
        with patch('corehq.apps.linked_domain.util.is_domain_in_active_link') as mock_active_link, \
            patch(
                'corehq.apps.linked_domain.util.user_has_admin_access_in_all_domains') as mock_admin:
            mock_active_link.return_value = False
            mock_admin.return_value = True
            result = is_domain_available_to_link('upstream', 'downstream', mock_user, should_enforce_admin=True)
        self.assertTrue(result)
