from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.users.models import WebUser
from corehq.privileges import LITE_RELEASE_MANAGEMENT, RELEASE_MANAGEMENT
from corehq.tabs.tabclasses import _get_release_management_items
from corehq.tabs.utils import path_starts_with_url

__test__ = {
    'url_starts_with_path': path_starts_with_url
}


class TestAccessToReleaseManagementTab(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = WebUser(username='test-username')

    def setUp(self):
        super().setUp()

        access_patcher = patch('corehq.tabs.tabclasses.can_user_access_linked_domains')
        self.mock_can_access = access_patcher.start()
        self.addCleanup(access_patcher.stop)

        privilege_patcher = patch('corehq.tabs.tabclasses.domain_has_privilege')
        self.mock_domain_has_privilege = privilege_patcher.start()
        self.addCleanup(privilege_patcher.stop)

        reverse_patcher = patch('corehq.tabs.tabclasses.reverse')
        self.mock_reverse = reverse_patcher.start()
        self.mock_reverse.return_value = 'dummy_url'
        self.addCleanup(reverse_patcher.stop)

    def test_returns_none_if_user_does_not_have_access(self):
        self.mock_can_access.return_value = False

        title, items = _get_release_management_items(self.user, "domain")

        self.assertFalse(title)
        self.assertFalse(items)

    def test_returns_erm_if_user_has_full_access(self):
        self.mock_can_access.return_value = True
        self.mock_domain_has_privilege.side_effect = lambda domain, privilege: privilege == RELEASE_MANAGEMENT

        title, items = _get_release_management_items(self.user, "domain")

        self.assertEqual(title, 'Enterprise Release Management')
        self.assertEqual(items[0]['title'], 'Linked Project Spaces')
        self.assertEqual(items[1]['title'], 'Linked Project Space History')

    def test_returns_mrm_if_user_has_lite_access(self):
        self.mock_can_access.return_value = True
        self.mock_domain_has_privilege.side_effect = lambda domain, privilege: privilege == LITE_RELEASE_MANAGEMENT

        title, items = _get_release_management_items(self.user, "domain")

        self.assertEqual(title, 'Multi-Environment Release Management')
        self.assertEqual(items[0]['title'], 'Linked Project Spaces')
        self.assertEqual(items[1]['title'], 'Linked Project Space History')
