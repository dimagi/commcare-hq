from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from corehq.apps.sms.models import QueuedSMS
from corehq.messaging.smsbackends.start_enterprise.exceptions import StartEnterpriseBackendException
from corehq.messaging.smsbackends.start_enterprise.models import (
    StartEnterpriseBackend,
    StartEnterpriseDeliveryReceipt,
)
from corehq.apps.sms.models import SMS
from django.test import TestCase
from mock import patch

SUCCESSFUL_RESPONSE = "919999999999-200904066072538"
RECOGNIZED_ERROR_MESSAGE = "Account Blocked"
UNRECOGNIZED_ERROR_MESSAGE = "Generic Error"


class TestStartEnterpriseBackendResponse(TestCase):

    def test_handle_success(self):
        backend = StartEnterpriseBackend()
        queued_sms = QueuedSMS(couch_id=uuid.uuid4().hex)

        backend.handle_response(queued_sms, 200, SUCCESSFUL_RESPONSE)
        dlr = StartEnterpriseDeliveryReceipt.objects.get(sms_id=queued_sms.couch_id)
        self.addCleanup(dlr.delete)
        self.assertEqual(dlr.message_id, SUCCESSFUL_RESPONSE)
        self.assertFalse(queued_sms.error)

    def test_handle_failure(self):
        backend = StartEnterpriseBackend()
        queued_sms = QueuedSMS()

        with patch('corehq.messaging.smsbackends.start_enterprise.models.notify_exception') as notify_patch:
            backend.handle_response(queued_sms, 200, RECOGNIZED_ERROR_MESSAGE)
            self.assertEqual(queued_sms.system_error_message, SMS.ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS)
            self.assertTrue(queued_sms.error)
            notify_patch.assert_called_once_with(
                None,
                "Error with the Start Enterprise Backend: %s" % RECOGNIZED_ERROR_MESSAGE
            )

        with self.assertRaisesMessage(
            StartEnterpriseBackendException,
            "Received unexpected status code: 500"
        ):
            backend.handle_response(queued_sms, 500, '')

        with self.assertRaisesMessage(
            StartEnterpriseBackendException,
            "Unrecognized response from Start Enterprise gateway: %s" % UNRECOGNIZED_ERROR_MESSAGE
        ):
            backend.handle_response(queued_sms, 200, UNRECOGNIZED_ERROR_MESSAGE)
