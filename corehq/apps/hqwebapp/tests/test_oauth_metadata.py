"""Tests for the RFC 8414 authorization server metadata well-known URLs.

HQ mounts ``oauth2_provider.urls`` under ``/oauth/``, so the issuer is
``https://<host>/oauth``. Strict RFC 8414 clients derive the metadata URL by
inserting ``/.well-known/oauth-authorization-server`` between the host and the
issuer's path, which must resolve at the domain root (see the
``oauth2_metadata`` mount in the root ``urls.py``).
"""

import json

from django.test import TestCase


class TestOAuthServerMetadataAtRoot(TestCase):

    def test_strict_rfc8414_url_with_issuer_path(self):
        response = self.client.get('/.well-known/oauth-authorization-server/oauth')
        assert response.status_code == 200
        metadata = json.loads(response.content)
        assert metadata['issuer'] == 'http://testserver/oauth'
        assert metadata['authorization_endpoint'] == 'http://testserver/oauth/authorize/'
        assert metadata['token_endpoint'] == 'http://testserver/oauth/token/'

    def test_prefixed_fallback_url_still_served(self):
        response = self.client.get('/oauth/.well-known/oauth-authorization-server')
        assert response.status_code == 200
        metadata = json.loads(response.content)
        assert metadata['issuer'] == 'http://testserver/oauth'
