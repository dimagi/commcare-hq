from unittest.mock import patch

from corehq.apps.linked_domain.util import (
    is_available_upstream_domain,
    is_domain_available_to_link,
)


@patch('corehq.apps.users.models.CouchUser')
class TestIsAvailableUpstreamDomain:

    def test_none_potential_upstream_domain_returns_false(self, mock_user):
        result = is_available_upstream_domain(None, 'downstream', mock_user)
        assert result is False

    def test_none_downstream_domain_returns_false(self, mock_user):
        result = is_available_upstream_domain('potential-upstream', None, mock_user)
        assert result is False

    def test_none_potential_upstream_and_none_downstream_returns_false(self, mock_user):
        result = is_available_upstream_domain(None, None, mock_user)
        assert result is False

    def test_same_domain_returns_false(self, mock_user):
        result = is_available_upstream_domain('domain', 'domain', mock_user)
        assert result is False

    def test_not_active_upstream_domain_returns_false(self, mock_user):
        with patch('corehq.apps.linked_domain.dbaccessors.is_active_upstream_domain') as mock_active_upstream:
            mock_active_upstream.return_value = False
            result = is_available_upstream_domain('potential-upstream', 'downstream', mock_user)
        assert result is False

    def test_user_without_access_returns_false(self, mock_user):
        with patch('corehq.apps.linked_domain.dbaccessors.is_active_upstream_domain') as mock_active_upstream,\
             patch('corehq.apps.linked_domain.util.user_has_access_in_all_domains') as mock_access:
            mock_active_upstream.return_value = True
            mock_access.return_value = False
            result = is_available_upstream_domain('potential-upstream', 'downstream', mock_user)
        assert result is False

    def test_user_with_access_returns_true(self, mock_user):
        with patch('corehq.apps.linked_domain.dbaccessors.is_active_upstream_domain') as mock_active_upstream, \
            patch(
                'corehq.apps.linked_domain.util.user_has_access_in_all_domains') as mock_access:
            mock_active_upstream.return_value = True
            mock_access.return_value = True
            result = is_available_upstream_domain('potential-upstream', 'downstream', mock_user)
        assert result is True


@patch('corehq.apps.users.models.CouchUser')
class TestIsDomainAvailableToLink:

    def test_none_upstream_domain_returns_false(self, mock_user):
        with self._available_to_link_patch():
            result = is_domain_available_to_link(None, 'domain', mock_user)
        assert result is False

    def test_none_candidate_domain_returns_false(self, mock_user):
        with self._available_to_link_patch():
            result = is_domain_available_to_link('domain', None, mock_user)
        assert result is False

    def test_none_upstream_and_none_candidate_domain_returns_false(self, mock_user):
        with self._available_to_link_patch():
            result = is_domain_available_to_link(None, None, mock_user)
        assert result is False

    def test_same_domain_returns_false(self, mock_user):
        with self._available_to_link_patch():
            result = is_domain_available_to_link('domain', 'domain', mock_user)
        assert result is False

    def test_domain_in_active_link_returns_false(self, mock_user):
        with self._available_to_link_patch(is_domain_in_active_link=True):
            result = is_domain_available_to_link('upstream', 'downstream', mock_user)
        assert result is False

    def test_user_without_access_returns_false(self, mock_user):
        with self._available_to_link_patch(user_has_access_in_all_domains=False):
            result = is_domain_available_to_link('upstream', 'downstream', mock_user)
        assert result is False

    def test_candidate_domain_without_access_returns_false(self, mock_user):
        with self._available_to_link_patch(can_domain_access_linked_domains=False):
            result = is_domain_available_to_link('upstream', 'downstream', mock_user)
        assert result is False

    def test_linkable_domain_returns_true(self, mock_user):
        with self._available_to_link_patch():
            result = is_domain_available_to_link('upstream', 'downstream', mock_user)
        assert result is True

    def _available_to_link_patch(
            self,
            is_domain_in_active_link=False,
            user_has_access_in_all_domains=True,
            can_domain_access_linked_domains=True,
        ):
        return patch.multiple(
            'corehq.apps.linked_domain.util',
            is_domain_in_active_link=lambda *args: is_domain_in_active_link,
            user_has_access_in_all_domains=lambda *args: user_has_access_in_all_domains,
            can_domain_access_linked_domains=lambda *args: can_domain_access_linked_domains,
        )
