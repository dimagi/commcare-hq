import time
from python_digest import build_authorization_request, calculate_nonce
from django.test import TestCase, Client
from django.conf import settings
from django.core.urlresolvers import reverse

from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, WebUser


class DigestOtaRestoreTest(TestCase):
    """
    Integration test for django_digest based ota restore is tested
    """
    domain = "test"
    wrong_domain = 'test-wrong-domain'
    username = "testota"
    web_username = 'test-webuser'
    password = "123"

    def setUp(self):
        create_domain(self.domain)
        create_domain(self.wrong_domain)
        self.commcare_user = CommCareUser.create(self.domain, self.username, self.password)
        self.web_user = WebUser.create(self.domain, self.web_username, self.password)

    def tearDown(self):
        self.commcare_user.delete()
        self.web_user.delete()
        delete_all_domains()

    def test_commcare_user_restore(self):
        uri = reverse('ota_restore', args=[self.domain])
        client = Client(HTTP_AUTHORIZATION=_get_http_auth_header(
            self.commcare_user.username,
            self.password,
            uri,
        ))

        resp = client.get(uri, follow=True)
        self.assertEqual(resp.status_code, 200)
        content = list(resp.streaming_content)[0]
        self.assertTrue("Successfully restored account {}!".format(self.username) in content)

    def test_web_user_restore(self):
        uri = reverse('ota_restore', args=[self.domain])
        client = Client(HTTP_AUTHORIZATION=_get_http_auth_header(
            self.web_user.username,
            self.password,
            uri,
        ))

        resp = client.get(uri, follow=True)
        self.assertEqual(resp.status_code, 200)
        content = list(resp.streaming_content)[0]
        self.assertTrue("Successfully restored account {}!".format(self.web_username) in content)

    def test_wrong_domain_web_user(self):
        uri = reverse('ota_restore', args=[self.wrong_domain])
        client = Client(HTTP_AUTHORIZATION=_get_http_auth_header(
            self.web_user.username,
            self.password,
            uri,
        ))

        resp = client.get(uri, follow=True)
        self.assertEqual(resp.status_code, 401)


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
