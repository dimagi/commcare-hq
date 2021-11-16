from unittest.mock import patch, Mock

from django.test import SimpleTestCase

from corehq.apps.domain.exceptions import DomainDoesNotExist
from corehq.apps.linked_domain.exceptions import DomainLinkError, DomainLinkAlreadyExists, DomainLinkNotAllowed
from corehq.apps.linked_domain.views import link_domains


class LinkDomainsTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(LinkDomainsTests, cls).setUpClass()
        cls.upstream_domain = 'upstream'
        cls.downstream_domain = 'downstream'

    def test_exception_raised_if_domain_does_not_exist(self):
        def mock_handler(domain):
            return domain != self.downstream_domain

        with patch('corehq.apps.linked_domain.views.domain_exists') as mock_domainexists,\
             self.assertRaises(DomainDoesNotExist):
            mock_domainexists.side_effect = mock_handler
            link_domains(Mock(), self.upstream_domain, self.downstream_domain)

    def test_exception_raised_if_domain_link_already_exists(self):
        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=Mock()),\
             self.assertRaises(DomainLinkAlreadyExists):
            link_domains(Mock(), self.upstream_domain, self.downstream_domain)

    def test_exception_raised_if_domain_link_error_raised(self):
        def mock_handler(downstream, upstream):
            raise DomainLinkError

        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=None),\
             patch('corehq.apps.linked_domain.views.DomainLink.link_domains') as mock_linkdomains,\
             self.assertRaises(DomainLinkError):
            mock_linkdomains.side_effect = mock_handler
            link_domains(Mock(), self.upstream_domain, self.downstream_domain)

    def test_exception_raised_if_user_is_not_admin_in_both_domains(self):
        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=None),\
             patch('corehq.apps.linked_domain.views.user_has_admin_access_in_all_domains', return_value=False),\
             self.assertRaises(DomainLinkNotAllowed):
            link_domains(Mock(), self.upstream_domain, self.downstream_domain)

    def test_successful(self):
        with patch('corehq.apps.linked_domain.views.domain_exists', return_value=True),\
             patch('corehq.apps.linked_domain.views.get_active_domain_link', return_value=None),\
             patch('corehq.apps.linked_domain.views.DomainLink.link_domains', return_value=True),\
             patch('corehq.apps.linked_domain.views.user_has_admin_access_in_all_domains', return_value=True):
            domain_link = link_domains(Mock(), self.upstream_domain, self.downstream_domain)

        self.assertIsNotNone(domain_link)
