# -*- coding: utf-8 -*-
from django.test import TestCase

from corehq.apps.sms.models import QueuedSMS
from corehq.messaging.smsbackends.vertex.models import VertexBackend

TEST_SUCCESSFUL_RESPONSE = "570737298-2017_05_27"
TEST_FAILURE_RESPONSE = "ES1001 Authentication Failed (invalid username/password)"


class TestVertexBackendResponseHandling(TestCase):
    def setUp(self):
        self.vertex_backend = VertexBackend()
        self.queued_sms = QueuedSMS()

    def handle_success(self):
        self.vertex_backend.handle_response(self.queued_sms, TEST_SUCCESSFUL_RESPONSE)
        self.assertEqual(self.queued_sms.backend_message_id, TEST_SUCCESSFUL_RESPONSE)
        self.assertFalse(self.queued_sms.error)

    def handle_failure(self):
        self.vertex_backend.handle_response(self.queued_sms, TEST_FAILURE_RESPONSE)
        self.assertEqual(self.queued_sms.system_error_message, TEST_FAILURE_RESPONSE)
        self.assertTrue(self.queued_sms.error)
