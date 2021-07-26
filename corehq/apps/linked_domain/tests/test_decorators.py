from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.linked_domain.util import can_access_linked_domains
from corehq.util.test_utils import flag_enabled


class TestCanAccessLinkedDomains(SimpleTestCase):

    def test_returns_false_if_no_user(self):
        result = can_access_linked_domains(None, 'test')
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_false_if_no_domain(self, mock_user):
        result = can_access_linked_domains(mock_user, None)
        self.assertFalse(result)

    def test_returns_false_if_no_user_and_no_domain(self):
        result = can_access_linked_domains(None, None)
        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_false_if_domain_has_privilege_but_user_is_not_admin(self, mock_user):
        mock_user.is_domain_admin = False

        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = True
            result = can_access_linked_domains(mock_user, 'test')

        self.assertFalse(result)

    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_true_if_domain_has_privilege_and_user_is_admin(self, mock_user):
        mock_user.is_domain_admin = True

        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = True
            result = can_access_linked_domains(mock_user, 'test')

        self.assertTrue(result)

    @flag_enabled("LINKED_DOMAINS")
    @patch('corehq.apps.users.models.CouchUser')
    def test_returns_true_if_domain_has_linked_domain_toggle_enabled(self, mock_user):
        with patch('corehq.apps.linked_domain.util.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            result = can_access_linked_domains(mock_user, 'test')

        self.assertTrue(result)
