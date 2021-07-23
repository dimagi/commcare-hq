from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.tabs.tabclasses import _get_release_management_items, _get_feature_flag_items
from corehq.tabs.utils import path_starts_with_url

__test__ = {
    'url_starts_with_path': path_starts_with_url
}

from corehq.util.test_utils import flag_enabled


class TestAccessToLinkedProjects(SimpleTestCase):

    @patch('corehq.apps.domain.models.Domain')
    def test_get_feature_flag_items_returns_none(self, mock_domain):

        with patch('corehq.tabs.tabclasses.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            items = _get_feature_flag_items(mock_domain)

        self.assertFalse(items)

    @flag_enabled('LINKED_DOMAINS')
    @patch('corehq.apps.domain.models.Domain')
    def test_get_feature_flag_items_returns_some(self, mock_domain):

        with patch('corehq.tabs.tabclasses.domain_has_privilege') as mock_domain_has_privilege, \
             patch('corehq.tabs.tabclasses.reverse') as mock_reverse:
            mock_domain_has_privilege.return_value = False
            mock_reverse.return_value = 'dummy_url'
            items = _get_feature_flag_items(mock_domain)

        self.assertTrue(items)

    @flag_enabled('LINKED_DOMAINS')
    @patch('corehq.apps.domain.models.Domain')
    def test_get_feature_flag_items_returns_none_if_domain_has_release_management_privilege(self, mock_domain):

        with patch('corehq.tabs.tabclasses.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = True
            items = _get_feature_flag_items(mock_domain)

        self.assertFalse(items)


class TestAccessToReleaseManagementTab(SimpleTestCase):

    @patch('corehq.apps.users.models.CouchUser')
    @patch('corehq.apps.domain.models.Domain')
    def test_get_release_management_items_returns_none(self, mock_user, mock_domain):
        mock_user.is_domain_admin.return_value = False

        with patch('corehq.tabs.tabclasses.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            items = _get_release_management_items(mock_user, mock_domain)

        self.assertFalse(items)

    @patch('corehq.apps.users.models.CouchUser')
    @patch('corehq.apps.domain.models.Domain')
    def test_get_release_management_items_returns_none_with_admin(self, mock_user, mock_domain):
        mock_user.is_domain_admin.return_value = True

        with patch('corehq.tabs.tabclasses.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            items = _get_release_management_items(mock_user, mock_domain)

        self.assertFalse(items)

    @patch('corehq.apps.users.models.CouchUser')
    @patch('corehq.apps.domain.models.Domain')
    def test_get_release_management_items_returns_none_with_domain_privilege(self, mock_user, mock_domain):
        mock_user.is_domain_admin.return_value = False

        with patch('corehq.tabs.tabclasses.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = True
            items = _get_release_management_items(mock_user, mock_domain)

        self.assertFalse(items)

    @patch('corehq.apps.users.models.CouchUser')
    @patch('corehq.apps.domain.models.Domain')
    def test_get_release_management_items_returns_some(self, mock_user, mock_domain):
        mock_user.is_domain_admin.return_value = True

        with patch('corehq.tabs.tabclasses.domain_has_privilege') as mock_domain_has_privilege, \
             patch('corehq.tabs.tabclasses.reverse') as mock_reverse:
            mock_domain_has_privilege.return_value = True
            mock_reverse.return_value = 'dummy_url'
            items = _get_release_management_items(mock_user, mock_domain)

        self.assertTrue(items)
