from __future__ import absolute_import
from __future__ import unicode_literals

from urllib import urlencode

from django.test import TestCase, override_settings
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.users.models import CommCareUser
from corehq.util.hmac_request import get_hmac_digest


@override_settings(FORMPLAYER_INTERNAL_AUTH_KEY='123abc', DEBUG=False)
class FormplayerRestoreTest(TestCase):
    """
    Test restores from Formplayer that aren't authed as a user (SMS forms)
    """
    domain = "test-fplayer"
    wrong_domain = 'test-wrong-domain'
    username = "testota"

    def setUp(self):
        create_domain(self.domain)
        create_domain(self.wrong_domain)
        self.commcare_user = CommCareUser.create(self.domain, self.username, '123')
        self.uri = reverse('ota_restore', args=[self.domain])
        self.uri_wrong_domain = reverse('ota_restore', args=[self.wrong_domain])

    def tearDown(self):
        self.commcare_user.delete()
        delete_all_domains()

    def test_commcare_user_restore(self):
        print(self.commcare_user.username, CommCareUser.get_by_username(self.commcare_user.username))
        resp = self._do_post({'version': 2.0, 'as_user': self.commcare_user.username})
        self.assertEqual(resp.status_code, 200)
        content = list(resp.streaming_content)[0]
        self.assertTrue("Successfully restored account {}!".format(self.username) in content)

    def _do_post(self, data):
        request_data = urlencode(data)
        hmac_header_value = get_hmac_digest(b'123abc', request_data)
        resp = self.client.post(
            self.uri, request_data, content_type='application/x-www-form-urlencoded',
            HTTP_X_MAC_DIGEST=hmac_header_value
        )
        return resp
