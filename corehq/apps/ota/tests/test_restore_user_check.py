from __future__ import absolute_import
from __future__ import unicode_literals
import base64
import uuid

from django.test import Client
from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser
from corehq.util import reverse


def _get_auth_header(username, password):
    return 'Basic ' + base64.b64encode('{}:{}'.format(username, password))


class UserCheckSyncTests(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = uuid.uuid4().hex
        cls.project = create_domain(cls.domain)
        cls.user = CommCareUser.create(cls.domain, 'mtest', 'abc')
        cls.auth_header = _get_auth_header('mtest', 'abc')
        cls.restore_uri = reverse('ota_restore', args=[cls.domain])

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()

    def test_restore_with_no_user_id(self):
        self._assert_restore_response_code(200, self.auth_header)

    def test_restore_with_user_id(self):
        self._assert_restore_response_code(200, self.auth_header, user_id=self.user.user_id)

    def test_restore_from_deleted_user(self):
        username = 'mtest1'
        password = '123'
        auth_header = _get_auth_header(username, password)

        original_user = CommCareUser.create(self.domain, username, password)
        original_user_id = original_user.user_id
        original_user.delete()

        # user deleted so can't auth
        self._assert_restore_response_code(401, auth_header)

        # create new user with same username and password
        new_user = CommCareUser.create(self.domain, username, password)

        # restore OK since user_id not passed so can't do check
        self._assert_restore_response_code(200, auth_header)

        # 412 since wrong user_id
        self._assert_restore_response_code(412, auth_header, user_id=original_user_id)
        self._assert_restore_response_code(200, auth_header, user_id=new_user.user_id)

    def _assert_restore_response_code(self, status_code, auth_header, user_id=None):
        client = Client(HTTP_AUTHORIZATION=auth_header)
        data = {}
        if user_id:
            data['user_id'] = user_id
        resp = client.get(self.restore_uri, data=data, follow=True)
        self.assertEqual(resp.status_code, status_code)
