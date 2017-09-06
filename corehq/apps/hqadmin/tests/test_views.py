import base64
import hashlib
import hmac
import json

from django.conf import settings
from django.http import HttpResponse
from django.test import SimpleTestCase
from django.test import TestCase
from django.test.client import Client
from django.test.utils import override_settings
from django.urls.base import reverse
from mock import patch, Mock

from corehq.apps.hqadmin.views import AdminRestoreView
from corehq.apps.users.models import CommCareUser
from corehq.util.test_utils import softer_assert


class AdminRestoreViewTests(SimpleTestCase):

    def test_get_context_data(self):
        user = Mock()
        user.domain = None
        app_id = None
        request = Mock()
        request.GET = {}
        request.openrosa_headers = {}
        timing_context = Mock()
        timing_context.to_list.return_value = []
        with patch('corehq.apps.hqadmin.views.get_restore_response',
                   return_value=(HttpResponse('bad response', status=500), timing_context)):

            view = AdminRestoreView(user=user, app_id=app_id, request=request)
            context = view.get_context_data(foo='bar', view='AdminRestoreView')
            self.assertEqual(context, {
                'foo': 'bar',
                'view': 'AdminRestoreView',
                'payload': '<error>Unexpected restore response 500: bad response. If you believe this is a bug '
                           'please report an issue.</error>\n',
                'restore_id': None,
                'status_code': 500,
                'timing_data': [],
                'num_cases': 0,
                'num_locations': 0,
            })


class SessionDetailsViewTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(SessionDetailsViewTest, cls).setUpClass()
        cls.couch_user = CommCareUser.create('toyland', 'bunkey', '123')
        cls.sql_user = cls.couch_user.get_django_user()

        client = Client()
        client.login(username='bunkey', password='123')

        session = client.session
        session.save()
        cls.session_key = session.session_key

        cls.url = reverse('session_details')

        cls.expected_response = {
            u'username': cls.sql_user.username,
            u'djangoUserId': cls.sql_user.pk,
            u'superUser': cls.sql_user.is_superuser,
            u'authToken': None,
            u'domains': [u'toyland'],
            u'anonymous': False
        }

    @classmethod
    def tearDownClass(cls):
        cls.couch_user.delete()
        super(SessionDetailsViewTest, cls).tearDownClass()

    @override_settings(DEBUG=True)
    @softer_assert()
    def test_session_details_view(self):
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})
        response = Client().post(self.url, data, content_type="application/json")
        self.assertEqual(200, response.status_code)
        self.assertJSONEqual(response.content, self.expected_response)

    @override_settings(FORMPLAYER_INTERNAL_AUTH_KEY='123abc', DEBUG=False)
    def test_with_hmac_signing(self):
        assert not settings.DEBUG
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})
        header_value = base64.b64encode(hmac.new('123abc', data, hashlib.sha256).digest())
        response = Client().post(
            self.url,
            data,
            content_type="application/json",
            HTTP_X_MAC_DIGEST=header_value
        )
        self.assertEqual(200, response.status_code)
        self.assertJSONEqual(response.content, self.expected_response)

    @override_settings(FORMPLAYER_INTERNAL_AUTH_KEY='123abc', DEBUG=False)
    def test_with_hmac_signing_fail(self):
        assert not settings.DEBUG
        data = json.dumps({'sessionId': self.session_key, 'domain': 'domain'})

        response = Client().post(
            self.url,
            data,
            content_type="application/json",
            HTTP_X_MAC_DIGEST='bad signature'
        )
        self.assertEqual(401, response.status_code)
