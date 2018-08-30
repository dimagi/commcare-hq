from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.models import QueuedSMS
from corehq.messaging.smsbackends.karix.exceptions import KarixError
from corehq.messaging.smsbackends.karix.models import KarixBackend
from django.test import TestCase


class MockResponse(object):

    def __init__(self, status_code, json_response):
        self.status_code = status_code
        self.json_response = json_response

    def json(self):
        return self.json_response


class KarixBackendTest(TestCase):

    def test_auth_key(self):
        backend = KarixBackend()
        backend.set_extra_fields(
            username='abc',
            password='123',
        )
        self.assertEqual(backend.get_auth_key(), b'YWJjOjEyMw==')

    def test_get_text_and_content_type(self):
        self.assertEqual(
            KarixBackend.get_text_and_content_type(QueuedSMS(text='abc')),
            ('abc', 'PM')
        )
        self.assertEqual(
            KarixBackend.get_text_and_content_type(QueuedSMS(text='\u0928\u092e\u0938\u094d\u0924\u0947')),
            ('\u0928\u092e\u0938\u094d\u0924\u0947', 'UC')
        )

    def test_handle_response(self):
        with self.assertRaises(KarixError):
            KarixBackend.handle_response(QueuedSMS(), MockResponse(500, {}))

        with self.assertRaises(KarixError):
            KarixBackend.handle_response(QueuedSMS(), MockResponse(200, {}))

        with self.assertRaises(KarixError):
            KarixBackend.handle_response(QueuedSMS(), MockResponse(200, {'status': {'code': '-999'}}))

        msg_obj = QueuedSMS()
        KarixBackend.handle_response(msg_obj, MockResponse(200, {'ackid': '123', 'status': {'code': '200'}}))
        self.assertEqual(msg_obj.backend_message_id, '123')
