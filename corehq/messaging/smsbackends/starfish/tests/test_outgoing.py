import requests_mock

from corehq.apps.sms.models import QueuedSMS, SMS
from corehq.messaging.smsbackends.starfish.models import (
    StarfishBackend,
    StarfishException,
)
from django.test import SimpleTestCase


class TestStarfishBackend(SimpleTestCase):

    def mock_send(self, **kwargs):
        msg = QueuedSMS(
            phone_number='+255111222333',
            text="the message",
        )
        msg.save = lambda: None  # prevent db access in SimpleTestCase
        with requests_mock.Mocker() as mock:
            mock.get(StarfishBackend.get_url(), **kwargs)
            StarfishBackend().send(msg)
        return msg

    def test_success(self):
        msg = self.mock_send(text="success=255111222333 18-10-18 21:01:30")
        self.assertFalse(msg.error)
        self.assertIsNone(msg.system_error_message)

    def test_invalid(self):
        msg = self.mock_send(text="invalid=255111222333 18-10-18 21:02:40")
        self.assertTrue(msg.error)
        self.assertEqual(msg.system_error_message, SMS.ERROR_INVALID_DESTINATION_NUMBER)

    def test_error(self):
        error_msg = "error, 255111222333 is not whitelisted 18-10-18 21:03:50"
        msg = self.mock_send(text=error_msg)
        self.assertTrue(msg.error)
        self.assertEqual(msg.system_error_message, SMS.ERROR_INVALID_DESTINATION_NUMBER)

    def test_500(self):
        with self.assertRaises(StarfishException) as err:
            self.mock_send(status_code=500)
        self.assertRegex(str(err.exception), r"response 500 from starfish")
