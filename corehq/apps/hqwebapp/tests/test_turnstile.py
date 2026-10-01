from unittest import mock

from django import forms
from django.core.exceptions import ValidationError
from django.test import RequestFactory, override_settings

import pytest
import requests
from unmagic import fixture, use

from corehq.apps.hqwebapp.fields import (
    TURNSTILE_SITEVERIFY_URL,
    TurnstileField,
)
from corehq.util.global_request.api import set_request


@fixture
def turnstile_keys():
    with override_settings(
        TURNSTILE_SITE_KEY='site-key', TURNSTILE_SECRET_KEY='secret-key'
    ):
        yield


@fixture
def siteverify():
    set_request(None)
    with mock.patch('corehq.apps.hqwebapp.fields.requests.post') as post:
        post.return_value = _turnstile_response(success=True)
        try:
            yield post
        finally:
            set_request(None)


def _turnstile_response(**payload):
    response = mock.Mock(spec=requests.Response)
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class ExampleForm(forms.Form):
    turnstile = TurnstileField()


@use(turnstile_keys, siteverify)
class TestTurnstileField:

    def test_accepts_a_token_turnstile_confirms(self):
        assert TurnstileField().clean('a-token') == 'a-token'

    def test_rejects_a_token_turnstile_refuses(self):
        siteverify().return_value = _turnstile_response(
            success=False, **{'error-codes': ['invalid-input-response']})

        with pytest.raises(ValidationError):
            TurnstileField().clean('a-token')

    @pytest.mark.parametrize('value', [None, ''], ids=['missing', 'blank'])
    def test_rejects_a_missing_token_without_asking_turnstile(self, value):
        with pytest.raises(ValidationError) as raised:
            TurnstileField().clean(value)

        assert raised.value.code == 'required'
        assert not siteverify().called

    def test_field_is_always_required(self):
        assert TurnstileField(required=False).required is True

    @pytest.mark.parametrize('value', ['a-token', None], ids=['token', 'none'])
    def test_is_inert_without_keys(self, value):
        with override_settings(TURNSTILE_SECRET_KEY=''):
            assert TurnstileField().clean(value) == value

        assert not siteverify().called

    def test_sends_token_and_respondent_ip_to_turnstile(self):
        set_request(RequestFactory().post('/', REMOTE_ADDR='203.0.113.7'))

        TurnstileField().clean('a-token')

        url, = siteverify().call_args.args
        assert url == TURNSTILE_SITEVERIFY_URL
        assert siteverify().call_args.kwargs['data'] == {
            'secret': 'secret-key',
            'response': 'a-token',
            'remoteip': '203.0.113.7',
        }
        assert siteverify().call_args.kwargs['timeout'] == 5

    def test_fails_closed_on_timeout(self):
        siteverify().side_effect = requests.Timeout()

        assert TurnstileField()._is_token_valid('a-token') is False

    def test_fails_closed_on_error_status(self):
        siteverify().return_value.raise_for_status.side_effect = requests.HTTPError()

        assert TurnstileField()._is_token_valid('a-token') is False


@use(turnstile_keys, siteverify)
class TestTurnstileWidget:

    def test_renders_with_attributes_javascript_expects(self):
        html = ExampleForm()['turnstile'].as_widget()

        assert 'class="cf-turnstile"' in html
        assert 'data-sitekey="site-key"' in html

    @pytest.mark.parametrize('prefix, name', [
        (None, 'turnstile'),
        ('signup', 'signup-turnstile'),
    ], ids=['unprefixed', 'prefixed'])
    def test_uses_form_defined_field_name(self, prefix, name):
        """Ensure the widget correctly overrides the default ``cf-turnstile-response``"""
        form = ExampleForm({name: 'a-token'}, prefix=prefix)

        assert f'data-response-field-name="{name}"' in form['turnstile'].as_widget()
        assert form.is_valid(), form.errors
        assert form.cleaned_data['turnstile'] == 'a-token'

    def test_renders_nothing_without_keys(self):
        with override_settings(TURNSTILE_SITE_KEY=''):
            assert ExampleForm()['turnstile'].as_widget().strip() == ''
