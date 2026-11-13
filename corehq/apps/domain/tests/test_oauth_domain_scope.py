from unittest.mock import MagicMock, patch

from django.http.request import HttpRequest
from django.http.response import HttpResponse
from django.test import RequestFactory

import pytest

from corehq.apps.domain.decorators import (
    _oauth2_check,
    _oauth_token_allows_request_domain,
)


def _make_request(token_domains=None, domain=None):
    request = HttpRequest()
    if token_domains is not None:
        request.oauth_token_domains = frozenset(token_domains)
    if domain is not None:
        request.domain = domain
    return request


class TestOauthTokenAllowsRequestDomain:

    def test_token_without_a_project_space_is_unrestricted(self):
        assert _oauth_token_allows_request_domain(_make_request(token_domains=[], domain='anything'))

    def test_matching_project_space_is_allowed(self):
        assert _oauth_token_allows_request_domain(
            _make_request(token_domains=['my-project'], domain='my-project')
        )

    def test_other_project_space_is_rejected(self):
        assert not _oauth_token_allows_request_domain(
            _make_request(token_domains=['my-project'], domain='other-project')
        )

    def test_project_agnostic_endpoint_is_allowed(self):
        """
        These are how a client discovers which projects it may use, so a
        restricted token must still reach them.
        """
        assert _oauth_token_allows_request_domain(_make_request(token_domains=['my-project']))

    @pytest.mark.parametrize('domain, allowed', [
        ('alpha', True),
        ('beta', True),
        ('gamma', False),
    ])
    def test_token_restricted_to_several_project_spaces(self, domain, allowed):
        request = _make_request(token_domains=['alpha', 'beta'], domain=domain)
        assert _oauth_token_allows_request_domain(request) is allowed


def _run_oauth_view(token_scope, domain=None):
    """Run a view behind ``_oauth2_check`` with a token carrying ``token_scope``."""
    request_info = MagicMock()
    request_info.access_token.scope = token_scope
    request = RequestFactory().get('/')
    if domain is not None:
        request.domain = domain

    oauthlib_core = MagicMock()
    oauthlib_core.verify_request.return_value = (True, request_info)

    with patch('corehq.apps.domain.decorators.get_oauthlib_core', return_value=oauthlib_core):
        wrapped = _oauth2_check(['access_apis'])(lambda req, *args, **kwargs: HttpResponse())
        return request, wrapped(request)


class TestOauth2CheckEnforcesProjectSpace:

    def test_restricted_token_reaches_its_own_project_space(self):
        _, response = _run_oauth_view('access_apis domain:my-project', domain='my-project')
        assert response.status_code == 200

    def test_restricted_token_is_forbidden_on_another_project_space(self):
        _, response = _run_oauth_view('access_apis domain:my-project', domain='other-project')
        assert response.status_code == 403

    def test_project_spaces_are_read_off_the_token(self):
        request, _ = _run_oauth_view('access_apis domain:my-project', domain='my-project')
        assert request.oauth_token_domains == frozenset({'my-project'})
