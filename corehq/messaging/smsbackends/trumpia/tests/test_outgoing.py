from django.test import SimpleTestCase

import requests_mock

from corehq.apps.sms.models import QueuedSMS
from corehq.messaging.smsbackends.trumpia.models import (
    TrumpiaBackend,
    TrumpiaRetry,
)


USERNAME = "testuser"
API_KEY = "123456789abc1011"


class TestTrumpiaBackend(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = TrumpiaBackend()
        cls.backend.extra_fields = {"username": USERNAME, "api_key": API_KEY}

    def test_success(self):
        msg = self.mock_send()
        self.assertEqual(msg.backend_message_id, "1234561234567asdf123")
        self.assertFalse(msg.error)
        self.assertIsNone(msg.system_error_message)

    def test_405(self):
        msg = self.mock_send(status_code=405)
        self.assertTrue(msg.error)
        self.assertEqual(msg.system_error_message, "Gateway error: 405")

    def test_500(self):
        with self.assertRaises(TrumpiaRetry) as err:
            self.mock_send(status_code=500)
        self.assertRegex(str(err.exception), "Gateway 500 error")

    def mock_send(self, status_code=200):
        msg = QueuedSMS(phone_number='+15554443333', text="the message")
        msg.save = lambda: None  # prevent db access in SimpleTestCase
        url = f"http://api.trumpia.com/rest/v1/{USERNAME}/sms"
        headers = {"X-ApiKey": API_KEY, "Content-Type": "application/json"}
        resp = {"request_id": "1234561234567asdf123", "sms_id": 987987987987}
        with requests_mock.Mocker() as mock:
            mock.put(
                url,
                request_headers=headers,
                status_code=status_code,
                json=(resp if status_code == 200 else {})
            )
            self.backend.send(msg)
        return msg
