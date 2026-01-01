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


@pytest.mark.parametrize('url,expected_case_id', [
    # v2 endpoints
    ('/a/test-domain/api/case/v2/', None),
    ('/a/test-domain/api/case/v2/simple-case-id/', 'simple-case-id'),
    ('/a/test-domain/api/case/v2/case-with-uuid-123/', 'case-with-uuid-123'),
    ('/a/test-domain/api/case/v2/id1,id2,id3/', 'id1,id2,id3'),  # commas supported
    # v0.6 endpoints
    ('/a/test-domain/api/v0.6/case/', None),
    ('/a/test-domain/api/v0.6/case/simple-case-id/', 'simple-case-id'),
    ('/a/test-domain/api/v0.6/case/id1,id2,id3/', 'id1,id2,id3'),  # commas supported
])
def test_case_id_url_patterns(url, expected_case_id):
    """Test that case_id URL patterns work with and without case_id parameter"""
    match = resolve(url)

    assert match.func == case_api
    assert match.kwargs['domain'] == 'test-domain'
    assert match.kwargs.get('case_id') == expected_case_id


@pytest.mark.parametrize('url', [
    # Invalid case_id values should not match the pattern [\w\-,]+
    '/a/test-domain/api/case/v2/id with spaces/',
    '/a/test-domain/api/case/v2/id@special/',
    '/a/test-domain/api/case/v2/id#hash/',
    '/a/test-domain/api/case/v2/id/with/slash/',
    '/a/test-domain/api/v0.6/case/id with spaces/',
    '/a/test-domain/api/v0.6/case/id@special/',
])
def test_case_id_rejects_invalid_characters(url):
    """Test that case_id pattern rejects invalid characters"""
    from django.urls.exceptions import Resolver404

    with pytest.raises(Resolver404):
        resolve(url)
