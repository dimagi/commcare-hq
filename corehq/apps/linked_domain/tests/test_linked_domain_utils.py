from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.linked_domain.util import (
    is_available_upstream_domain,
    is_domain_available_to_link,
)


class TestIsAvailableUpstreamDomain(SimpleTestCase):

    @patch('corehq.apps.users.models.CouchUser')
    def test_none_potential_upstream_domain_returns_false(self, mock_user):
        result = is_available_upstream_domain(None, 'downstream', mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_none_downstream_domain_returns_false(self, mock_user):
        result = is_available_upstream_domain('potential-upstream', None, mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_none_potential_upstream_and_none_downstream_returns_false(self, mock_user):
        result = is_available_upstream_domain(None, None, mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_same_domain_returns_false(self, mock_user):
        result = is_available_upstream_domain('domain', 'domain', mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_not_active_upstream_domain_returns_false(self, mock_user):
        with patch('corehq.apps.linked_domain.dbaccessors.is_active_upstream_domain') as mock_active_upstream:
            mock_active_upstream.return_value = False
            result = is_available_upstream_domain('potential-upstream', 'downstream', mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_user_without_admin_access_returns_false(self, mock_user):
        with patch('corehq.apps.linked_domain.dbaccessors.is_active_upstream_domain') as mock_active_upstream,\
             patch('corehq.apps.linked_domain.util.user_has_admin_access_in_all_domains') as mock_admin:
            mock_active_upstream.return_value = True
            mock_admin.return_value = False
            result = is_available_upstream_domain('potential-upstream', 'downstream', mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_user_with_admin_access_returns_true(self, mock_user):
        with patch('corehq.apps.linked_domain.dbaccessors.is_active_upstream_domain') as mock_active_upstream, \
            patch(
                'corehq.apps.linked_domain.util.user_has_admin_access_in_all_domains') as mock_admin:
            mock_active_upstream.return_value = True
            mock_admin.return_value = True
            result = is_available_upstream_domain('potential-upstream', 'downstream', mock_user)
        self.assertTrue(result)


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
    def test_user_without_admin_access_returns_false(self, mock_user):
        with patch('corehq.apps.linked_domain.util.is_domain_in_active_link') as mock_active_link,\
             patch('corehq.apps.linked_domain.util.user_has_admin_access_in_all_domains') as mock_admin:
            mock_active_link.return_value = False
            mock_admin.return_value = False
            result = is_domain_available_to_link('upstream', 'downstream', mock_user)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_user_with_admin_access_returns_true(self, mock_user):
        with patch('corehq.apps.linked_domain.util.is_domain_in_active_link') as mock_active_link, \
            patch(
                'corehq.apps.linked_domain.util.user_has_admin_access_in_all_domains') as mock_admin:
            mock_active_link.return_value = False
            mock_admin.return_value = True
            result = is_domain_available_to_link('upstream', 'downstream', mock_user)
        self.assertTrue(result)
