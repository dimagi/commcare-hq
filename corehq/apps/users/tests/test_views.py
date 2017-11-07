from __future__ import absolute_import
import json
from django.test import TestCase
from django.urls import reverse

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.views.mobile.users import MobileWorkerListView
from corehq.apps.users.models import WebUser, CouchUser
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.const import ANONYMOUS_USERNAME
from corehq.util.test_utils import flag_enabled


class TestMobileWorkerListView(TestCase):
    domain = 'mobile-worker-list-view'
    web_username = 'test-webuser'
    password = '***'

    def setUp(self):
        self.project = create_domain(self.domain)
        self.web_user = WebUser.create(self.domain, self.web_username, self.password)

        # We aren't testing permissions for this test
        self.web_user.is_superuser = True
        self.web_user.save()

    def tearDown(self):
        self.project.delete()
        delete_all_users()

    def _remote_invoke(self, route, data):
        self.client.login(username=self.web_username, password=self.password)
        return self.client.post(
            reverse(MobileWorkerListView.urlname, args=[self.domain]),
            json.dumps(data),
            content_type='application/json;charset=UTF-8',
            HTTP_DJNG_REMOTE_METHOD=route,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_create_mobile_worker(self):
        resp = self._remote_invoke('create_mobile_worker', {
            "mobileWorker": {
                "first_name": "Test",
                "last_name": "Test",
                "username": "test.test",
                "password": "123"
            }
        })
        content = json.loads(resp.content)
        self.assertEqual(content['success'], True)
        user = CouchUser.get_by_username(
            '{}@{}.commcarehq.org'.format(
                'test.test',
                self.domain,
            )
        )
        self.assertFalse(user.is_anonymous)

    @flag_enabled('ANONYMOUS_WEB_APPS_USAGE')
    def test_create_anonymous_mobile_worker(self):
        resp = self._remote_invoke('create_mobile_worker', {
            'mobileWorker': {
                'first_name': 'Test',
                'last_name': 'Test',
                'username': 'test.test',
                'password': '123',
                'is_anonymous': True,
            },
        })
        content = json.loads(resp.content)
        self.assertEqual(content['success'], True)

        user = CouchUser.get_by_username(
            '{}@{}.commcarehq.org'.format(
                ANONYMOUS_USERNAME,
                self.domain,
            )
        )
        self.assertTrue(user.is_anonymous)

    def test_check_username_for_anonymous(self):
        resp = self._remote_invoke('check_username', {
            'username': ANONYMOUS_USERNAME
        })
        content = json.loads(resp.content)
        self.assertTrue('error' in content)
