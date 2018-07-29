from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.models import QueuedSMS
from corehq.messaging.smsbackends.ivory_coast_mtn.exceptions import IvoryCoastMTNError
from corehq.messaging.smsbackends.ivory_coast_mtn.models import IvoryCoastMTNBackend
from django.test import TestCase

SUCCESS_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<SendResult xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xmlns="http://pmmsoapmessenger.com/">
  <Result>OK</Result>
  <TransactionID>164b210b-748c-41d2-97f4-88d166415423</TransactionID>
</SendResult>"""

ERROR_RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<SendResult xmlns:xsd="http://www.w3.org/2001/XMLSchema"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xmlns="http://pmmsoapmessenger.com/">
  <Result>FAILED</Result>
  <TransactionID>1756d6f2-e15f-4397-9670-47b98e92ba62</TransactionID>
</SendResult>"""


class TestIvoryCoastMTNBackendResponse(TestCase):

    def test_handle_success(self):
        backend = IvoryCoastMTNBackend()
        queued_sms = QueuedSMS()

        backend.handle_response(queued_sms, 200, SUCCESS_RESPONSE)
        self.assertEqual(queued_sms.backend_message_id, '164b210b-748c-41d2-97f4-88d166415423')

    def test_handle_failure(self):
        backend = IvoryCoastMTNBackend()
        queued_sms = QueuedSMS()

        with self.assertRaises(IvoryCoastMTNError):
            backend.handle_response(queued_sms, 200, ERROR_RESPONSE)
        self.assertEqual(queued_sms.backend_message_id, '1756d6f2-e15f-4397-9670-47b98e92ba62')

    def test_get_result_and_transaction_id(self):
        self.assertEqual(
            IvoryCoastMTNBackend.get_result_and_transaction_id(SUCCESS_RESPONSE),
            {'result': 'OK', 'transaction_id': '164b210b-748c-41d2-97f4-88d166415423'}
        )
