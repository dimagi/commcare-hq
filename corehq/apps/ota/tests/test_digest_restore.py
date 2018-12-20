from __future__ import absolute_import
from __future__ import unicode_literals
import time

import mock
from django.http import HttpResponse

from python_digest import build_authorization_request, calculate_nonce
from django.test import TestCase, Client
from django.conf import settings
from django.urls import reverse

from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.util.test_utils import flag_enabled


class DigestOtaRestoreTest(TestCase):
    """
    Integration test for django_digest based ota restore is tested
    """
    domain = "test"
    wrong_domain = 'test-wrong-domain'
    username = "testota"
    web_username = 'test-webuser'
    password = "123"

    @classmethod
    def setUpClass(cls):
        super(DigestOtaRestoreTest, cls).setUpClass()
        create_domain(cls.domain)
        create_domain(cls.wrong_domain)
        cls.commcare_user = CommCareUser.create(cls.domain, cls.username, cls.password)
        cls.web_user = WebUser.create(cls.domain, cls.web_username, cls.password)

    @classmethod
    def tearDownClass(cls):
        cls.commcare_user.delete()
        cls.web_user.delete()
        delete_all_domains()
        super(DigestOtaRestoreTest, cls).tearDownClass()

    @mock.patch('corehq.apps.ota.views.get_restore_response')
    def test_commcare_user_restore(self, mock_restore):
        # mock for the sake for fast running test
        mock_restore.return_value = (HttpResponse('Success', status=200), None)
        uri, client = self._set_restore_client(self.domain, self.commcare_user.username)
        resp = client.get(uri, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode('utf-8'), "Success")

    @mock.patch('corehq.apps.ota.views.get_restore_response')
    def test_web_user_restore(self, mock_restore):
        # mock for the sake for fast running test
        mock_restore.return_value = (HttpResponse('Success', status=200), None)
        uri, client = self._set_restore_client(self.domain, self.web_user.username)
        resp = client.get(uri, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode('utf-8'), "Success")

    def test_wrong_domain_web_user(self):
        uri, client = self._set_restore_client(self.wrong_domain, self.web_user.username)
        resp = client.get(uri, follow=True)
        self.assertEqual(resp.status_code, 401)

    @flag_enabled('DATA_MIGRATION')
    def test_web_user_restore_during_migration(self):
        uri, client = self._set_restore_client(self.domain, self.web_user.username)
        resp = client.get(uri, follow=True)
        self.assertEqual(resp.status_code, 503)

    def _set_restore_client(self, with_domain, auth_username):
        uri = reverse('ota_restore', args=[with_domain])
        client = Client(HTTP_AUTHORIZATION=_get_http_auth_header(
            auth_username,
            self.password,
            uri,
        ))
        return uri, client


def _get_http_auth_header(username, password, uri):
    return build_authorization_request(
        username,
        'GET',
        uri,
        3,
        nonce=calculate_nonce(time.time(), settings.SECRET_KEY),
        realm='DJANGO',
        opaque='myopaque',
        password=password,
    )
