# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals
import six
from django.test import TestCase

from corehq.apps.sms.models import QueuedSMS
from corehq.messaging.smsbackends.vertex.models import VertexBackend
from corehq.apps.sms.util import strip_plus
from corehq.messaging.smsbackends.vertex.const import (
    TEXT_MSG_TYPE,
    UNICODE_MSG_TYPE,
)

TEST_USERNAME = "test-vertex"
TEST_PASSWORD = "test-password"
TEST_SENDER_ID = "test-sender-id"
TEST_PHONE_NUMBER = "+919999999999"
TEST_TEXT_MESSAGE = "THIS IS A TEXT MESSAGE."
TEST_UNICODE_MESSAGE = "शब्दों का डर is a message with symbols ##,,++&&"


class TestVertexBackendRequestContent(TestCase):
    def setUp(self):
        self.vertex_backend = VertexBackend()
        self.vertex_backend.set_extra_fields(
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            senderid=TEST_SENDER_ID,
        )
        self.queued_sms = QueuedSMS(
            phone_number=TEST_PHONE_NUMBER,
        )

    def test_params(self):
        self.queued_sms.text = TEST_TEXT_MESSAGE
        params = self.vertex_backend.populate_params(self.queued_sms)
        self.assertEqual(params['username'], TEST_USERNAME)
        self.assertEqual(params['pass'], TEST_PASSWORD)
        self.assertEqual(params['senderid'], TEST_SENDER_ID)
        self.assertEqual(params['response'], 'Y')
        self.assertEqual(params['dest_mobileno'], strip_plus(TEST_PHONE_NUMBER))
        self.assertEqual(params['msgtype'], TEXT_MSG_TYPE)
        self.assertEqual(params['message'].decode('ascii'), TEST_TEXT_MESSAGE)

        self.queued_sms.text = TEST_UNICODE_MESSAGE
        params = self.vertex_backend.populate_params(self.queued_sms)
        self.assertEqual(params['message'].decode('utf-8'), TEST_UNICODE_MESSAGE)
        self.assertEqual(params['msgtype'], UNICODE_MSG_TYPE)

    def test_phone_number_is_valid(self):
        self.assertFalse(VertexBackend().phone_number_is_valid('+91'))
        self.assertFalse(VertexBackend().phone_number_is_valid('+123456789'))
        self.assertTrue(VertexBackend().phone_number_is_valid('+910123456789'))
