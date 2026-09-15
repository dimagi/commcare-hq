import pytest
import requests
import requests_mock
from django.test import override_settings
from unmagic import fixture

from corehq.apps.hqadmin.offboarding.clients import (
    OffboardingClientError,
    PlatformOffboardingClient,
    normalize_email,
)

STUB_USERS = 'https://stub.example.com/users'


class StubClient(PlatformOffboardingClient):
    slug = 'stub'
    name = 'Stub'
    default_config = {'api_url': 'https://stub.example.com/', 'region': 'us'}
    required_config = ('token', 'secret')

    def find_account(self, email):
        return self._request('GET', f"{self.config['api_url']}users", params={'email': email})


STUB_CONFIGURED = {'stub': {'token': 't', 'secret': 's'}}


@fixture
def stub_http():
    with override_settings(OFFBOARDING_PLATFORMS=STUB_CONFIGURED), requests_mock.Mocker() as m:
        yield m


def test_normalize_email():
    assert normalize_email('  Jane@Dimagi.COM ') == 'jane@dimagi.com'
    assert normalize_email(None) == ''


def test_config_merges_deployment_values_over_defaults():
    with override_settings(OFFBOARDING_PLATFORMS={'stub': {'token': 't', 'secret': 's', 'region': 'eu'}}):
        assert StubClient().config == {
            'api_url': 'https://stub.example.com/', 'region': 'eu', 'token': 't', 'secret': 's'}


def test_none_values_do_not_mask_defaults():
    with override_settings(OFFBOARDING_PLATFORMS={'stub': {'token': 't', 'secret': 's', 'region': None}}):
        assert StubClient().config['region'] == 'us'


def test_missing_platform_entry_leaves_defaults_only():
    with override_settings(OFFBOARDING_PLATFORMS={}):
        client = StubClient()
        assert client.config == StubClient.default_config
        assert not client.is_configured


@pytest.mark.parametrize('missing_key', ['token', 'secret'])
def test_is_configured_requires_every_required_key(missing_key):
    with override_settings(OFFBOARDING_PLATFORMS=STUB_CONFIGURED):
        assert StubClient().is_configured
    partial = {'stub': {k: v for k, v in STUB_CONFIGURED['stub'].items() if k != missing_key}}
    with override_settings(OFFBOARDING_PLATFORMS=partial):
        assert not StubClient().is_configured


@stub_http
def test_transport_error_is_wrapped_and_chained():
    stub_http().get(STUB_USERS, exc=requests.ConnectTimeout)
    with pytest.raises(OffboardingClientError, match='Stub: could not reach the API') as excinfo:
        StubClient().find_account('jane@dimagi.com')
    assert isinstance(excinfo.value.__cause__, requests.ConnectTimeout)


@stub_http
def test_unexpected_status_is_wrapped_and_truncated():
    stub_http().get(STUB_USERS, status_code=403, text='{"errors": ["' + 'x' * 500 + '"]}')
    with pytest.raises(OffboardingClientError) as excinfo:
        StubClient().find_account('jane@dimagi.com')
    message = str(excinfo.value)
    assert message.startswith('Stub returned HTTP 403: ')
    assert message.endswith('…')
    assert len(message) < 260


@stub_http
def test_expected_status_is_returned():
    stub_http().get(STUB_USERS, json={'data': []})
    response = StubClient().find_account('jane@dimagi.com')
    assert response.status_code == 200


@stub_http
def test_requests_carry_a_timeout():
    m = stub_http()
    m.get(STUB_USERS, json={'data': []})
    StubClient().find_account('jane@dimagi.com')
    assert m.last_request.timeout == 15
