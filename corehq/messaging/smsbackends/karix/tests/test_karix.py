import json
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
        self.assertEqual(backend.get_auth_key(), 'YWJjOjEyMw==')

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

    def test_get_json_payload_unicode(self):
        backend = KarixBackend()
        backend.set_extra_fields(
            username='abc',
            password='123',
            sender_id='SENDER',
        )

        msg_obj = QueuedSMS(text='\u0928\u092e\u0938\u094d\u0924\u0947', phone_number='+919999999999')
        payload = backend.get_json_payload(msg_obj)
        self.assertEqual(
            json.loads(json.dumps(payload)),
            {
                'ver': '1.0',
                'key': 'YWJjOjEyMw==',
                'messages': [
                    {
                        'dest': ['919999999999'],
                        'send': 'SENDER',
                        'text': '\u0928\u092e\u0938\u094d\u0924\u0947',
                        'type': 'UC',
                        'vp': '1440',
                    },
                ],
            }
        )

    def test_get_json_payload_ascii(self):
        backend = KarixBackend()
        backend.set_extra_fields(
            username='abc',
            password='123',
            sender_id='SENDER',
        )

        msg_obj = QueuedSMS(text='test', phone_number='+919999999999')
        payload = backend.get_json_payload(msg_obj)
        self.assertEqual(
            json.loads(json.dumps(payload)),
            {
                'ver': '1.0',
                'key': 'YWJjOjEyMw==',
                'messages': [
                    {
                        'dest': ['919999999999'],
                        'send': 'SENDER',
                        'text': 'test',
                        'type': 'PM',
                        'vp': '1440',
                    },
                ],
            }
        )
