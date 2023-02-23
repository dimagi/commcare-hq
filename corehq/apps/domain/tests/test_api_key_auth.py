from django.test import RequestFactory

from nose.tools import assert_equal

from corehq.apps.domain.auth import HQApiKeyAuthentication

USERNAME = "joel@lastofus.com"
API_KEY = "123abc"


def has_credentials(request):
    actual = HQApiKeyAuthentication().extract_credentials(request)
    return actual == (USERNAME, API_KEY)


def test_no_auth():
    request = RequestFactory().get('/myapi/')
    assert not has_credentials(request)


def test_credentials_in_META():
    request = RequestFactory().get('/myapi/')
    request.META['HTTP_AUTHORIZATION'] = f"ApiKey {USERNAME}:{API_KEY}"
    assert has_credentials(request)


def test_credentials_in_GET():
    request = RequestFactory().get(f'/myapi/?username={USERNAME}&api_key={API_KEY}')
    assert has_credentials(request)


def test_credentials_in_POST():
    request = RequestFactory().post('/myapi/', {'username': USERNAME, 'api_key': API_KEY})
    assert has_credentials(request)
