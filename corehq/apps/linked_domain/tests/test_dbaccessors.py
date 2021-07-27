from unittest.mock import patch

from django.test import SimpleTestCase

from corehq.apps.linked_domain.dbaccessors import (
    get_available_domains_to_link,
    get_available_upstream_domains_for_downstream_domain,
)
from corehq.util.test_utils import flag_enabled


class TestGetAvailableUpstreamDomainsForDownstreamDomain(SimpleTestCase):

    @patch('corehq.apps.users.models.CouchUser')
    @patch('corehq.apps.accounting.models.BillingAccount')
    def test_no_privilege_or_feature_flag_returns_none(self, mock_user, mock_account):
        mock_account.get_domains.return_value = ['upstream', 'downstream-1', 'downstream-2']
        with patch('corehq.apps.linked_domain.dbaccessors.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            upstream_domains = get_available_upstream_domains_for_downstream_domain(
                'downstream-1', mock_user, mock_account
            )
        self.assertFalse(upstream_domains)

    @flag_enabled("LINKED_DOMAINS")
    @patch('corehq.apps.users.models.CouchUser')
    @patch('corehq.apps.accounting.models.BillingAccount')
    def test_release_management_privilege_returns_domains_for_account(self, mock_user, mock_account):
        """NOTE: this also tests that the release_management privilege overrides the linked domains flag"""
        mock_account.get_domains.return_value = ['upstream', 'downstream-1', 'downstream-2']
        expected_upstream_domains = ['upstream']
        with patch('corehq.apps.linked_domain.dbaccessors.domain_has_privilege') as mock_domain_has_privilege,\
             patch('corehq.apps.linked_domain.dbaccessors.get_available_upstream_domains_for_account') \
             as mock_account_domains,\
             patch('corehq.apps.linked_domain.dbaccessors.get_available_upstream_domains_for_user') \
             as mock_user_domains:
            mock_domain_has_privilege.return_value = True
            mock_account_domains.return_value = expected_upstream_domains
            mock_user_domains.return_value = ['wrong']
            upstream_domains = get_available_upstream_domains_for_downstream_domain(
                'downstream-1', mock_user, mock_account
            )
        self.assertEqual(expected_upstream_domains, upstream_domains)

    @flag_enabled("LINKED_DOMAINS")
    @patch('corehq.apps.users.models.CouchUser')
    @patch('corehq.apps.accounting.models.BillingAccount')
    def test_linked_domains_flag_returns_domains_for_user(self, mock_user, mock_account):
        expected_upstream_domains = ['upstream']
        with patch('corehq.apps.linked_domain.dbaccessors.domain_has_privilege') as mock_domain_has_privilege,\
             patch('corehq.apps.linked_domain.dbaccessors.get_available_upstream_domains_for_account') \
             as mock_account_domains,\
             patch('corehq.apps.linked_domain.dbaccessors.get_available_upstream_domains_for_user') \
             as mock_user_domains:
            mock_domain_has_privilege.return_value = False
            mock_account_domains.return_value = ['wrong']
            mock_user_domains.return_value = expected_upstream_domains
            upstream_domains = get_available_upstream_domains_for_downstream_domain(
                'downstream-1', mock_user, mock_account
            )

        self.assertEqual(expected_upstream_domains, upstream_domains)


class TestGetAvailableDomainsToLink(SimpleTestCase):

    @patch('corehq.apps.users.models.CouchUser')
    @patch('corehq.apps.accounting.models.BillingAccount')
    def test_no_privilege_or_feature_flag_returns_none(self, mock_user, mock_account):
        mock_account.get_domains.return_value = ['upstream', 'downstream-1', 'downstream-2']
        with patch('corehq.apps.linked_domain.dbaccessors.domain_has_privilege') as mock_domain_has_privilege:
            mock_domain_has_privilege.return_value = False
            domains = get_available_domains_to_link('upstream', mock_user, mock_account)

        self.assertEqual([], domains)

    @flag_enabled("LINKED_DOMAINS")
    @patch('corehq.apps.users.models.CouchUser')
    @patch('corehq.apps.accounting.models.BillingAccount')
    def test_release_management_privilege_returns_domains_for_account(self, mock_user, mock_account):
        """NOTE: this also tests that the release_management privilege overrides the linked domains flag"""
        expected_domains = ['downstream-1', 'downstream-2']
        with patch('corehq.apps.linked_domain.dbaccessors.domain_has_privilege') as mock_domain_has_privilege,\
             patch('corehq.apps.linked_domain.dbaccessors.get_available_domains_to_link_for_account') \
             as mock_account_domains,\
             patch('corehq.apps.linked_domain.dbaccessors.get_available_domains_to_link_for_user') \
             as mock_user_domains:
            mock_domain_has_privilege.return_value = True
            mock_account_domains.return_value = expected_domains
            mock_user_domains.return_value = ['wrong']
            domains = get_available_domains_to_link('upstream', mock_user, mock_account)

        self.assertEqual(expected_domains, domains)

    @flag_enabled("LINKED_DOMAINS")
    @patch('corehq.apps.users.models.CouchUser')
    @patch('corehq.apps.accounting.models.BillingAccount')
    def test_linked_domains_flag_returns_domains_for_user(self, mock_user, mock_account):
        expected_domains = ['downstream-1', 'downstream-2']
        with patch('corehq.apps.linked_domain.dbaccessors.domain_has_privilege') as mock_domain_has_privilege,\
             patch('corehq.apps.linked_domain.dbaccessors.get_available_domains_to_link_for_account') \
             as mock_account_domains,\
             patch('corehq.apps.linked_domain.dbaccessors.get_available_domains_to_link_for_user') \
             as mock_user_domains:
            mock_domain_has_privilege.return_value = False
            mock_account_domains.return_value = ['wrong']
            mock_user_domains.return_value = expected_domains
            domains = get_available_domains_to_link('upstream', mock_user, mock_account)

        self.assertEqual(expected_domains, domains)
