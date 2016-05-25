import time
from python_digest import build_authorization_request, calculate_nonce
from django.test import TestCase
from django.conf import settings

from corehq.apps.domain.models import Domain
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser


class DigestOtaRestoreTest(TestCase):
    """
    Integration test for django_digest based ota restore is tested
    """
    domain = "test"
    username = "testota"
    first_name = "ota"
    last_name = "restorer"
    password = "123"

    def setUp(self):
        create_domain(self.domain)
        self.couch_user = CommCareUser.create(self.domain, self.username, self.password)
        self.couch_user.first_name = self.first_name
        self.couch_user.last_name = self.last_name
        self.couch_user.save()

    def tearDown(self):
        self.couch_user.delete()
        domain = Domain.get_by_name(self.domain)
        domain.delete()

    def testOtaRestore(self, password=None):
        uri = '/a/%s/phone/restore/' % self.domain
        self.client.defaults['HTTP_AUTHORIZATION'] = build_authorization_request(
            self.couch_user.username,
            'GET',
            uri,
            3,
            nonce=calculate_nonce(time.time(), settings.SECRET_KEY),
            realm='DJANGO',
            opaque='myopaque',
            password=self.password,
        )

        resp = self.client.get(uri, follow=True)
        self.assertEqual(resp.status_code, 200)
        content = list(resp.streaming_content)[0]
        self.assertTrue("Successfully restored account {}!".format(self.username) in content)
