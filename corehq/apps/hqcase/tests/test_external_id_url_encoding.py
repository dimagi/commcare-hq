"""
Test that the path converter allows any characters in the Case API
`external_id` parameter.
"""
from urllib.parse import unquote

from django.urls import resolve

import pytest

from corehq.apps.hqcase.views import case_api


@pytest.mark.parametrize('url_path,expected_external_id', [
    ('hello-world', 'hello-world'),
    ('hello%20world', 'hello world'),
    ('hello%40world', 'hello@world'),
    ('hello%23world', 'hello#world'),
    ('hello%3Fworld', 'hello?world'),
    ('hello%26world', 'hello&world'),
    ('hello%3Dworld', 'hello=world'),
    ('hello%2Bworld', 'hello+world'),
    ('hello%2Fworld', 'hello/world'),
    ('hello%E2%80%94world%2F', 'hello—world/'),
])
def test_external_id_url_decoding_v2(url_path, expected_external_id):
    url = f'/a/test-domain/api/case/v2/ext/{url_path}/'
    match = resolve(url)

    assert match.func == case_api
    assert match.kwargs['domain'] == 'test-domain'
    assert unquote(match.kwargs['external_id']) == expected_external_id


@pytest.mark.parametrize('url_path,expected_external_id', [
    ('hello-world', 'hello-world'),
    ('hello%2Fworld', 'hello/world'),
    ('hello%E2%80%94world%2F', 'hello—world/'),
])
def test_external_id_url_decoding_v0_6(url_path, expected_external_id):
    url = f'/a/test-domain/api/v0.6/case/ext/{url_path}/'
    match = resolve(url)

    assert match.func == case_api
    assert match.kwargs['domain'] == 'test-domain'
    assert unquote(match.kwargs['external_id']) == expected_external_id
