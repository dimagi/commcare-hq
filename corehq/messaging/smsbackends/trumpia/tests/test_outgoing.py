from urllib.parse import urlencode

from django.test import SimpleTestCase

import requests_mock

from corehq.apps.reports.standard.message_event_display import (
    get_sms_status_display,
)
from corehq.apps.sms.models import QueuedSMS
from corehq.messaging.smsbackends.trumpia.models import (
    TrumpiaBackend,
    TrumpiaRetry,
)


USERNAME = "testuser"
API_KEY = "123456789abc1011"


class TestTrumpiaBackend(SimpleTestCase):
    """Trumpia SMS backend

    Error status code reference:
    https://classic.trumpia.com/api/docs/http/status-code/direct-sms.php
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backend = TrumpiaBackend()
        cls.backend.extra_fields = {"username": USERNAME, "api_key": API_KEY}

    def test_success(self):
        msg = self.mock_send()
        self.assertEqual(msg.backend_message_id, "1234561234567asdf123")
        self.assertIsNone(msg.system_error_message)
        self.assertFalse(msg.error)
        self.assertEqual(get_sms_status_display(msg), "Sent")

    def test_success_status_pending(self):
        msg = self.mock_send(report={
            "requestID": "1234561234567asdf123",
            "message": "In progress",
        })
        self.assertEqual(msg.backend_message_id, "1234561234567asdf123")
        self.assertTrue(msg.is_status_pending())
        self.assertEqual(get_sms_status_display(msg),
            "Sent message ID: 1234561234567asdf123")

    def test_fail_missing_requestID(self):
        msg = self.mock_send(response={"boo": "hoo"})
        self.assertIsNone(msg.backend_message_id)
        self.assertEqual(msg.system_error_message, "Gateway error: {'boo': 'hoo'}")
        self.assertTrue(msg.error)

    def test_fail_missing_statuscode(self):
        msg = self.mock_send(report={"unexpected": "result"})
        self.assertEqual(msg.backend_message_id, "1234561234567asdf123")
        self.assertEqual(msg.system_error_message,
            "Gateway error: {'unexpected': 'result'}")
        self.assertTrue(msg.error)

    def test_generic_failure(self):
        msg = self.mock_send(
            response={"requestID": "1234561234567asdf123"},
            report={"statuscode": "0", "message": "Did not send."},
        )
        self.assertEqual(msg.backend_message_id, "1234561234567asdf123")
        self.assertEqual(msg.system_error_message,
            "Gateway error: status 0: Did not send.")
        self.assertTrue(msg.error)

    def test_fail_MRME0201(self):
        msg = self.mock_send(
            response={"requestID": "1234561234567asdf123"},
            report={"statuscode": "MRME0201", "message": "Internal Error."},
        )
        self.assertEqual(msg.backend_message_id, "1234561234567asdf123")
        self.assertEqual(msg.system_error_message,
            "Gateway error: status MRME0201: Internal Error.")
        self.assertTrue(msg.error)

    def test_405(self):
        msg = self.mock_send(status_code=405)
        self.assertEqual(msg.system_error_message, "Gateway error: 405")
        self.assertTrue(msg.error)

    def test_500(self):
        with self.assertRaises(TrumpiaRetry) as err:
            self.mock_send(status_code=500)
        self.assertRegex(str(err.exception), "Gateway 500 error")

    def test_get_message_details(self):
        request_id = "1234561234567asdf123"
        report = {"statuscode": "1", "message": "Send Success"}
        with requests_mock.Mocker() as mock:
            self.mock_report(mock, request_id, report)
            self.backend.get_message_details(request_id)

    def mock_send(self, status_code=200, response=None, report=None):
        msg = QueuedSMS(
            phone_number='+15554443333',
            text="the message",
            direction="O",
        )
        msg.save = lambda: None  # prevent db access in SimpleTestCase
        query = querystring({
            "apikey": API_KEY,
            "country_code": "0",
            "mobile_number": msg.phone_number,
            "message": msg.text,
            "concat": "TRUE",
        })
        if response is None:
            response = {"requestID": "1234561234567asdf123"}
        with requests_mock.Mocker() as mock:
            mock.get(
                "http://api.trumpia.com/http/v2/sendverificationsms" + query,
                request_headers={"Accept": "application/json"},
                status_code=status_code,
                json=(response if status_code == 200 else {}),
            )
            if "requestID" in response:
                self.mock_report(mock, response["requestID"], report)
            self.backend.send(msg)
        return msg

    def mock_report(self, mock, request_id, report):
        query = querystring({"request_id": request_id})
        if not report:
            report = {
                "statuscode": "1",
                "message": "Send Success",
                "creditProcessID": "12345",
                "taskID": "123456",
            }
        mock.get(
            "https://api.trumpia.com/http/v2/checkresponse" + query,
            request_headers={"Accept": "application/json"},
            status_code=200,
            json=report
        )


def querystring(data):
    return "?" + urlencode(data)
