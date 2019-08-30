

from django.http.response import HttpResponse
from django.test import TestCase, override_settings
from django.urls import reverse

import mock
import six

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

    @classmethod
    def setUpClass(cls):
        super(FormplayerRestoreTest, cls).setUpClass()
        create_domain(cls.domain)
        create_domain(cls.wrong_domain)
        cls.commcare_user = CommCareUser.create(cls.domain, cls.username, '123')
        cls.uri = reverse('ota_restore', args=[cls.domain])
        cls.uri_wrong_domain = reverse('ota_restore', args=[cls.wrong_domain])

    @classmethod
    def tearDownClass(cls):
        cls.commcare_user.delete()
        delete_all_domains()
        super(FormplayerRestoreTest, cls).tearDownClass()

    @mock.patch('corehq.apps.ota.views.get_restore_response')
    def test_commcare_user_restore(self, mock_restore):
        # mock for the sake for fast running test
        mock_restore.return_value = (HttpResponse('Success', status=200), None)
        resp = self._do_post({'version': 2.0, 'as': self.commcare_user.username})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.decode('utf-8'), "Success")

    def test_missing_as_user_param(self):
        resp = self._do_post({'version': 2.0})
        self.assertEqual(resp.status_code, 401)

    def test_bad_user(self):
        resp = self._do_post({'version': 2.0, 'as': 'non-user'})
        self.assertEqual(resp.status_code, 401)

    def test_wrong_domain(self):
        resp = self._do_post({'version': 2.0, 'as': self.commcare_user.username}, uri=self.uri_wrong_domain)
        self.assertEqual(resp.status_code, 403)

    def test_bad_hmac(self):
        resp = self._do_post({'version': 2.0, 'as': self.commcare_user.username}, hmac='bad')
        self.assertEqual(resp.status_code, 401)

    def _do_post(self, data, uri=None, hmac=None):
        uri = uri or self.uri
        params = six.moves.urllib.parse.urlencode(data)
        # have to format url with params directly to ensure ordering remains unchanged
        full_url = '{}?{}'.format(uri, params)
        hmac_header_value = hmac or get_hmac_digest(b'123abc', full_url)
        return self.client.get(full_url, HTTP_X_MAC_DIGEST=hmac_header_value)
