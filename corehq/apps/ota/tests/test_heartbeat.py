from __future__ import absolute_import

from __future__ import unicode_literals
import base64
from datetime import datetime
from uuid import uuid4

from django.test import TestCase
from django.urls.base import reverse
from unittest2.case import skip

from corehq.apps.app_manager.models import Application
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser


@skip("temporarily disabled")
class HeartbeatTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(HeartbeatTests, cls).setUpClass()
        cls.domain = create_domain(uuid4().hex)
        cls.user = CommCareUser.create(cls.domain.name, 'user1', '123')
        cls.app, cls.build = cls._create_app_and_build()
        cls.url = reverse('phone_heartbeat', args=[cls.domain.name, cls.build.get_id])

    @classmethod
    def _create_app_and_build(cls):
        app = Application.new_app(cls.domain.name, 'app')
        app.save()
        build = app.make_build()
        build.save(increment_version=False)
        return app, build

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        super(HeartbeatTests, cls).tearDownClass()

    def _auth_headers(self, user):
        return {
            'HTTP_AUTHORIZATION': 'Basic ' + base64.b64encode('%s:123' % user.username),
        }

    def _do_request(self, user, device_id, app_id=None, app_version=1, last_sync='',
                    unsent_forms=0, quarantined_forms=0, cc_version='2.39', url=None,
                    response_code=200):
        url = url or self.url
        resp = self.client.get(url, {
            'app_id': app_id or self.app.get_id,
            'app_version': app_version,
            'device_id': device_id,
            'last_sync_time': last_sync,
            'num_unsent_forms': unsent_forms,
            'num_quarantined_forms': quarantined_forms,
            'cc_version': cc_version
        }, **self._auth_headers(user))
        self.assertEqual(resp.status_code, response_code)

    def test_heartbeat(self):
        self._do_request(
            self.user,
            device_id='123123',
            app_version=1,
            last_sync=datetime.utcnow().isoformat(),
            unsent_forms=2,
            quarantined_forms=3
        )
        device = CommCareUser.get(self.user.get_id).get_device('123123')
        self.assertEqual(device.device_id, '123123')
        self.assertIsNotNone(device.last_used)
        self.assertEqual(device.commcare_version, '2.39')
        self.assertEqual(1, len(device.app_meta))

        app_meta = device.app_meta[0]
        self.assertEqual(app_meta.app_id, self.app.get_id)
        self.assertEqual(app_meta.build_id, self.build.get_id)
        self.assertEqual(app_meta.build_id, self.build.get_id)
        self.assertEqual(app_meta.build_version, 1)
        self.assertIsNotNone(app_meta.last_heartbeat)
        self.assertEqual(app_meta.last_request, app_meta.last_heartbeat)
        self.assertEqual(app_meta.num_unsent_forms, 2)
        self.assertEqual(app_meta.num_quarantined_forms, 3)
        self.assertIsNotNone(app_meta.last_sync)

    def test_blank_last_sync(self):
        self._do_request(
            self.user,
            device_id='2',
            last_sync='',
        )
        device = CommCareUser.get(self.user.get_id).get_device('2')
        self.assertIsNone(device.get_meta_for_app(self.app.get_id).last_sync)

    def test_bad_app_id(self):
        url = reverse('phone_heartbeat', args=[self.domain.name, 'bad_id'])
        self._do_request(self.user, device_id='test_bad_app_id', app_id='no-app', url=url, response_code=404)
        device = CommCareUser.get(self.user.get_id).get_device('test_bad_app_id')
        self.assertIsNone(device)
