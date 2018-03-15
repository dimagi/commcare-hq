# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from django.test import mock

from corehq.apps.sms.models import QueuedSMS
from corehq.messaging.smsbackends.vertex.exceptions import VertexBackendException
from corehq.messaging.smsbackends.vertex.models import VertexBackend
from corehq.apps.sms.models import SMS

TEST_SUCCESSFUL_RESPONSE = "570737298-2017_05_27"
TEST_FAILURE_RESPONSE = "ES1001 Authentication Failed (invalid username/password)"
TEST_NON_CODE_MESSAGES = "Account is Expire"
TEST_INCORRECT_NUMBER_RESPONSE = "ES1009 Sorry unable to process request"
RANDOM_ERROR_MESSAGE = "Bond.. James Bond.."


class TestVertexBackendResponseHandling(TestCase):
    def setUp(self):
        self.vertex_backend = VertexBackend()
        self.queued_sms = QueuedSMS()

    def test_handle_success(self):
        self.vertex_backend.handle_response(self.queued_sms, 200, TEST_SUCCESSFUL_RESPONSE)
        self.assertEqual(self.queued_sms.backend_message_id, TEST_SUCCESSFUL_RESPONSE)
        self.assertFalse(self.queued_sms.error)

    def test_handle_failure(self):
        self.assertFalse(self.queued_sms.error)
        self.vertex_backend.handle_response(self.queued_sms, 200, TEST_INCORRECT_NUMBER_RESPONSE)
        self.assertEqual(self.queued_sms.system_error_message, SMS.ERROR_INVALID_DESTINATION_NUMBER)
        self.assertTrue(self.queued_sms.error)

        with mock.patch('corehq.messaging.smsbackends.vertex.models.notify_exception') as exception_notifier:
            self.queued_sms.error = False
            self.vertex_backend.handle_response(self.queued_sms, 200, TEST_NON_CODE_MESSAGES)
            self.assertEqual(self.queued_sms.system_error_message, SMS.ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS)
            self.assertTrue(self.queued_sms.error)
            exception_notifier.assert_called_once_with(
                None,
                "Error with the Vertex SMS Backend: " + TEST_NON_CODE_MESSAGES
            )

        with mock.patch('corehq.messaging.smsbackends.vertex.models.notify_exception') as exception_notifier:
            self.queued_sms.error = False
            self.vertex_backend.handle_response(self.queued_sms, 200, TEST_FAILURE_RESPONSE)
            self.assertEqual(self.queued_sms.system_error_message, SMS.ERROR_TOO_MANY_UNSUCCESSFUL_ATTEMPTS)
            self.assertTrue(self.queued_sms.error)
            exception_notifier.assert_called_once_with(
                None,
                "Error with the Vertex SMS Backend: " + TEST_FAILURE_RESPONSE
            )

        with self.assertRaisesMessage(
                VertexBackendException,
                "Unrecognized response from Vertex gateway with {response_status_code} "
                "status code, response {response_text}".format(
                    response_status_code=200,
                    response_text=RANDOM_ERROR_MESSAGE)
        ):
            self.vertex_backend.handle_response(self.queued_sms, 200, RANDOM_ERROR_MESSAGE)
