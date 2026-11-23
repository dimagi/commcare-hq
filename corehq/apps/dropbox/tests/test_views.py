from unittest.mock import patch

import pytest
from django.test import RequestFactory

from corehq.apps.dropbox.utils import DROPBOX_CSRF_TOKEN
from corehq.apps.dropbox.views import DropboxAuthCallback
from corehq.apps.hqwebapp.views import dropbox_next_url


@pytest.mark.parametrize('referer, expected', [
    ('http://testserver/a/test-domain/data/export/', 'http://testserver/a/test-domain/data/export/'),
    ('https://example.com/', '/'),
    (None, '/'),
])
def test_dropbox_next_url(referer, expected):
    headers = {'HTTP_REFERER': referer} if referer is not None else {}
    request = RequestFactory().get('/dropbox/upload/abc/', **headers)
    assert dropbox_next_url(request, 'abc') == expected


@pytest.mark.parametrize('next_url, expected', [
    ('/a/test-domain/data/export/', '/a/test-domain/data/export/'),
    ('https://example.com/', '/'),
    (None, '/'),
])
def test_dropbox_auth_callback_redirect(next_url, expected):
    request = RequestFactory().get('/dropbox/finalize/')
    request.session = {DROPBOX_CSRF_TOKEN: 'token'}
    if next_url is not None:
        request.session['dropbox_next_url'] = next_url
    with patch('corehq.apps.dropbox.views.get_dropbox_auth_flow'):
        response = DropboxAuthCallback.as_view()(request)
    assert response.status_code == 302
    assert response['Location'] == expected
