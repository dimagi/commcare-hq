from unittest.mock import patch, Mock

from django.test import SimpleTestCase

from corehq.apps.linked_domain.exceptions import DomainLinkError
from corehq.apps.linked_domain.views import handle_create_domain_link_request


class CreateDomainLinkRequestTests(SimpleTestCase):

    def test_fails_if_domain_does_not_exist(self):
        upstream_domain = 'upstream'
        downstream_domain = 'downstream'
        user = Mock()

        def mock_handler(domain):
            return domain != downstream_domain

        with patch('corehq.apps.linked_domain.views.domain_exists') as mock_domainexists:
            mock_domainexists.side_effect = mock_handler
            error = handle_create_domain_link_request(user, upstream_domain, downstream_domain)

        self.assertEqual(error, f"The project space {downstream_domain} does not exist. Make sure "
                                f"the name is correct and that this domain hasn't been deleted.")

    def test_fails_if_domain_link_already_exists(self):
        upstream_domain = 'upstream'
        downstream_domain = 'downstream'
        user = Mock()

        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=Mock()):
            error = handle_create_domain_link_request(user, upstream_domain, downstream_domain)

        self.assertEqual(error, f"The project space {downstream_domain} is already a downstream "
                                f"project space of {upstream_domain}.")

    def test_fails_if_domain_link_error_raised(self):
        upstream_domain = 'upstream'
        downstream_domain = 'downstream'
        user = Mock()

        def mock_handler(downstream, upstream):
            raise DomainLinkError

        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=None),\
             patch('corehq.apps.linked_domain.views.DomainLink.link_domains') as mock_linkdomains:
            mock_linkdomains.side_effect = mock_handler
            error = handle_create_domain_link_request(user, upstream_domain, downstream_domain)

        self.assertEqual(error, f"An error was encountered while attempting to link {downstream_domain} to "
                                f"{upstream_domain}.")

    def test_fails_if_user_is_not_admin_in_both_domains(self):
        upstream_domain = 'upstream'
        downstream_domain = 'downstream'
        user = Mock()

        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=None),\
             patch('corehq.apps.linked_domain.views.user_has_admin_access_in_all_domains', return_value=False):
            error = handle_create_domain_link_request(user, upstream_domain, downstream_domain)

        self.assertEqual(error, "The user must be an admin is both project spaces to successfully create a link.")

    def test_successful(self):
        upstream_domain = 'upstream'
        downstream_domain = 'downstream'
        user = Mock()

        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=None),\
             patch('corehq.apps.linked_domain.views.DomainLink.link_domains', return_value=True),\
             patch('corehq.apps.linked_domain.views.user_has_admin_access_in_all_domains', return_value=True):
            error = handle_create_domain_link_request(user, upstream_domain, downstream_domain)

        self.assertIsNone(error)
