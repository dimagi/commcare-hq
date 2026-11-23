import inspect
from unittest.mock import Mock

import pytest
from django.test import RequestFactory

from corehq.apps.sso.models import IdentityProvider
from corehq.apps.sso.utils.url_helpers import get_saml_login_url
from corehq.apps.sso.views.saml import (
    _get_relay_state_redirect_url,
    sso_saml_login,
)

IDP = IdentityProvider(slug='test-idp')


@pytest.mark.parametrize('relay_state, expected', [
    ('/a/test-domain/dashboard/', '/a/test-domain/dashboard/'),
    ('https://testserver/a/test-domain/', 'https://testserver/a/test-domain/'),
    ('https://example.com/', None),
    ('//example.com/', None),
    ('https:///example.com/', None),
    ('javascript:alert(1)', None),
    ('https://testserver', None),  # self URL
    (get_saml_login_url(IDP), None),
    (None, None),
])
def test_relay_state_redirect_url(relay_state, expected):
    data = {'RelayState': relay_state} if relay_state is not None else {}
    request = RequestFactory().post('/sso/test-idp/acs/', data, HTTP_HOST='testserver')
    request.idp = IDP
    request.saml2_request_data = {
        'https': 'on',
        'http_host': 'testserver',
        'script_name': request.path,
        'get_data': {},
        'post_data': request.POST.copy(),
    }
    assert _get_relay_state_redirect_url(request) == expected


@pytest.mark.parametrize('next_url, expected', [
    ('/a/test-domain/dashboard/', '/a/test-domain/dashboard/'),
    ('https://example.com/', None),
    ('https:///example.com/', None),
    (None, None),
])
def test_saml_login_return_to(next_url, expected):
    params = {'next': next_url} if next_url is not None else {}
    request = RequestFactory().get('/sso/test-idp/login/', params)
    request.saml2_auth = Mock()
    request.saml2_auth.login.return_value = 'https://idp.example.com/login'
    view = inspect.unwrap(sso_saml_login)
    view(request, 'test-idp')
    request.saml2_auth.login.assert_called_once_with(return_to=expected, force_authn=True)
