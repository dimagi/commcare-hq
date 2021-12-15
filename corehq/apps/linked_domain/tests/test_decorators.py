from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.linked_domain.util import can_user_access_release_management, can_domain_access_release_management
from corehq.util.test_utils import flag_enabled


class TestCanUserAccessReleaseManagement(SimpleTestCase):

    def test_returns_false_if_no_user(self):
        result = can_user_access_release_management(None, 'test')
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_false_if_no_domain(self, mock_user):
        result = can_user_access_release_management(mock_user, None)
        self.assertFalse(result)

    def test_returns_false_if_no_user_and_no_domain(self):
        result = can_user_access_release_management(None, None)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_false_if_domain_has_privilege_but_user_is_not_admin(self, mock_user):
        mock_user.is_domain_admin.return_value = False

        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = True
            result = can_user_access_release_management(mock_user, 'test')

        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_true_if_domain_has_privilege_and_user_is_admin(self, mock_user):
        mock_user.is_domain_admin.return_value = True

        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = True
            result = can_user_access_release_management(mock_user, 'test')

        self.assertTrue(result)

    @flag_enabled("LINKED_DOMAINS")
    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_false_if_domain_has_linked_domain_toggle_enabled_and_check_toggle_is_false(self, mock_user):
        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            result = can_user_access_release_management(mock_user, 'test')

        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_false_if_domain_has_no_linked_domain_toggle_enabled_and_check_toggle_is_true(self, mock_user):
        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            result = can_user_access_release_management(mock_user, 'test', check_toggle=True)

        self.assertFalse(result)

    @flag_enabled("LINKED_DOMAINS")
    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_true_if_domain_has_linked_domain_toggle_enabled_and_check_toggle_is_true(self, mock_user):
        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            result = can_user_access_release_management(mock_user, 'test', check_toggle=True)

        self.assertTrue(result)


class TestCanDomainAccessReleaseManagement(SimpleTestCase):

    def test_returns_false_if_no_domain(self):
        result = can_domain_access_release_management(None)
        self.assertFalse(result)

    def test_returns_true_if_domain_has_release_management_privilege(self):
        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = True
            result = can_domain_access_release_management('test')

        self.assertTrue(result)

    @flag_enabled("LINKED_DOMAINS")
    def test_returns_false_if_domain_has_linked_domain_toggle_enabled_and_check_toggle_is_false(self):
        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            result = can_domain_access_release_management('test')

        self.assertFalse(result)

    def test_returns_false_if_domain_has_no_linked_domain_toggle_enabled_and_check_toggle_is_true(self):
        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            result = can_domain_access_release_management('test', check_toggle=True)

        self.assertFalse(result)

    @flag_enabled("LINKED_DOMAINS")
    def test_returns_true_if_domain_has_linked_domain_toggle_enabled_and_check_toggle_is_true(self):
        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            result = can_domain_access_release_management('test', check_toggle=True)

        self.assertTrue(result)
