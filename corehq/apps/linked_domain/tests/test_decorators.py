from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.linked_domain.util import can_user_access_linked_domains, can_domain_access_linked_domains
from corehq.privileges import LITE_RELEASE_MANAGEMENT, RELEASE_MANAGEMENT


class TestCanUserAccessLinkedDomains(SimpleTestCase):

    def test_returns_false_if_no_user(self):
        result = can_user_access_linked_domains(None, 'test')
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_false_if_no_domain(self, mock_user):
        result = can_user_access_linked_domains(mock_user, None)
        self.assertFalse(result)

    def test_returns_false_if_no_user_and_no_domain(self):
        result = can_user_access_linked_domains(None, None)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_false_if_has_privilege_but_no_access(self, mock_user):
        """
        Regardless of privilege, if user does not have permission, this method should always return false
        """
        mock_user.is_domain_admin.return_value = False
        mock_user.has_permission.return_value = False

        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = True
            result = can_user_access_linked_domains(mock_user, 'test')

        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_true_if_has_release_management_and_is_admin(self, mock_user):
        mock_user.is_domain_admin.return_value = True
        mock_user.has_permission.return_value = False

        def mock_handler(domain, privilege):
            return privilege == RELEASE_MANAGEMENT

        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.side_effect = mock_handler
            result = can_user_access_linked_domains(mock_user, 'test')

        self.assertTrue(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_true_if_has_release_management_and_has_permission(self, mock_user):
        mock_user.is_domain_admin.return_value = False
        mock_user.has_permission.return_value = True

        def mock_handler(domain, privilege):
            return privilege == RELEASE_MANAGEMENT

        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.side_effect = mock_handler
            result = can_user_access_linked_domains(mock_user, 'test')

        self.assertTrue(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_true_if_has_lite_release_management_and_is_admin(self, mock_user):
        mock_user.is_domain_admin.return_value = True
        mock_user.has_permission.return_value = False

        def mock_handler(domain, privilege):
            return privilege == LITE_RELEASE_MANAGEMENT

        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.side_effect = mock_handler
            result = can_user_access_linked_domains(mock_user, 'test')

        self.assertTrue(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_true_if_has_lite_release_management_and_has_permission(self, mock_user):
        mock_user.is_domain_admin.return_value = False
        mock_user.has_permission.return_value = True

        def mock_handler(domain, privilege):
            return privilege == LITE_RELEASE_MANAGEMENT

        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.side_effect = mock_handler
            result = can_user_access_linked_domains(mock_user, 'test')

        self.assertTrue(result)


class TestCanDomainAccessLinkedDomains(SimpleTestCase):

    def test_returns_false_if_no_domain(self):
        result = can_domain_access_linked_domains(None)
        self.assertFalse(result)

    def test_returns_true_if_domain_has_release_management_privilege(self):
        def mock_handler(domain, privilege):
            return privilege == RELEASE_MANAGEMENT

        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.side_effect = mock_handler
            result = can_domain_access_linked_domains('test')

        self.assertTrue(result)

    def test_returns_false_if_domain_does_not_have_release_management_privilege(self):
        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            result = can_domain_access_linked_domains('test')

        self.assertFalse(result)

    def test_returns_true_if_domain_has_lite_release_management_and_include_lite_version_is_true(self):
        def mock_handler(domain, privilege):
            return privilege == LITE_RELEASE_MANAGEMENT

        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.side_effect = mock_handler
            # include_lite_version is True by default
            result = can_domain_access_linked_domains('test')

        self.assertTrue(result)

    def test_returns_false_if_domain_does_not_have_lite_release_management_and_include_lite_version_is_true(self):
        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            # include_lite_version is True by default
            result = can_domain_access_linked_domains('test')

        self.assertFalse(result)

    def test_returns_false_if_domain_has_lite_release_management_and_include_lite_version_is_false(self):
        def mock_handler(domain, privilege):
            return privilege == LITE_RELEASE_MANAGEMENT
        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.side_effect = mock_handler
            result = can_domain_access_linked_domains('test', include_lite_version=False)

        self.assertFalse(result)
