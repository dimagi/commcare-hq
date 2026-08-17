import doctest
from unittest.mock import patch

import pytest

from corehq.apps.hqwebapp import oauth_scopes
from corehq.apps.hqwebapp.oauth_scopes import (
    DOMAIN_SCOPE_PREFIX,
    HQScopes,
    ScopeDescriptions,
    domain_scope,
    token_domains,
)
from corehq.apps.users.models import CouchUser

STATIC_SCOPES = {'access_apis', 'reports:view', 'mobile_access', 'sync'}


class FakeOAuthRequest:
    """Stands in for the oauthlib ``Request`` passed to ``get_available_scopes``."""

    def __init__(self, scopes=None, user=None):
        self.scopes = scopes
        self.user = user


class FakeCouchUser:
    def __init__(self, domains):
        self.domains = domains

    def is_member_of(self, domain, allow_enterprise=False):
        return domain in self.domains


def _member_of(*domains):
    """Stand the requesting user in for one belonging to ``domains``."""
    return patch.object(CouchUser, 'from_django_user', return_value=FakeCouchUser(domains))


def test_doctests():
    results = doctest.testmod(oauth_scopes)
    assert results.failed == 0


def test_domain_scope():
    assert domain_scope('my-project') == 'domain:my-project'


@pytest.mark.parametrize('scope_string, expected', [
    ('', frozenset()),
    ('access_apis', frozenset()),
    ('access_apis domain:alpha', frozenset({'alpha'})),
    ('access_apis domain:alpha domain:beta', frozenset({'alpha', 'beta'})),
    ('domain:alpha', frozenset({'alpha'})),
    # Whitespace-separated, in any order, with duplicates collapsed.
    ('  domain:alpha   access_apis  domain:alpha ', frozenset({'alpha'})),
    # A scope that merely contains the prefix is not a domain scope.
    ('access_apis notdomain:alpha', frozenset()),
])
def test_token_domains(scope_string, expected):
    assert token_domains(scope_string) == expected


@pytest.mark.parametrize('scope_string', [None, 42, object(), ['domain:alpha']])
def test_token_domains_ignores_non_strings(scope_string):
    assert token_domains(scope_string) == frozenset()


def test_token_domains_fails_closed_on_empty_domain():
    """
    A bare ``domain:`` yields an unmatchable restriction rather than no restriction.

    Such a scope is not grantable, so this only matters if one is written directly
    to the database. Denying every project space is the safe reading.
    """
    assert token_domains('access_apis domain:') == frozenset({''})


class TestScopeDescriptions:

    def test_static_scopes_pass_through(self):
        descriptions = ScopeDescriptions({'access_apis': 'Access CommCare API data'})
        assert descriptions['access_apis'] == 'Access CommCare API data'

    def test_domain_scope_is_synthesized(self):
        descriptions = ScopeDescriptions()
        assert 'my-project' in descriptions[f'{DOMAIN_SCOPE_PREFIX}my-project']

    def test_unknown_scope_raises(self):
        descriptions = ScopeDescriptions()
        with pytest.raises(KeyError):
            descriptions['bogus']


class TestHQScopes:

    def test_get_all_scopes_supports_domain_lookup(self):
        all_scopes = HQScopes().get_all_scopes()
        assert STATIC_SCOPES.issubset(all_scopes.keys())
        assert 'my-project' in all_scopes[f'{DOMAIN_SCOPE_PREFIX}my-project']

    def test_available_scopes_without_a_request(self):
        """OIDC discovery calls this with no arguments; it must not raise."""
        assert set(HQScopes().get_available_scopes()) == STATIC_SCOPES

    def test_available_scopes_without_a_requested_domain(self):
        request = FakeOAuthRequest(scopes=['access_apis'])
        assert set(HQScopes().get_available_scopes(request=request)) == STATIC_SCOPES

    def test_unauthenticated_authorize_step_permits_a_valid_project_space(self):
        """
        The GET authorize step has no resource owner, so the consent screen can
        render for any syntactically valid project space.
        """
        request = FakeOAuthRequest(scopes=['access_apis', 'domain:my-project'], user=None)
        assert 'domain:my-project' in HQScopes().get_available_scopes(request=request)

    @pytest.mark.parametrize('domain', ['has space', 'has/slash', '', 'has?query'])
    def test_syntactically_invalid_project_space_is_rejected(self, domain):
        request = FakeOAuthRequest(scopes=[f'{DOMAIN_SCOPE_PREFIX}{domain}'], user=None)
        available = HQScopes().get_available_scopes(request=request)
        assert set(available) == STATIC_SCOPES

    @pytest.mark.parametrize('requested, granted', [
        (['domain:mine'], {'domain:mine'}),
        (['domain:not-mine'], set()),
        (['domain:mine', 'domain:not-mine'], {'domain:mine'}),
    ])
    def test_only_project_spaces_the_user_belongs_to_are_grantable(self, requested, granted):
        request = FakeOAuthRequest(scopes=requested, user=object())
        with _member_of('mine'):
            available = HQScopes().get_available_scopes(request=request)
        assert set(available) == STATIC_SCOPES | granted
