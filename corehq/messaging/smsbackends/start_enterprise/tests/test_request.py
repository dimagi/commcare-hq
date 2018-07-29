from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.sms.models import QueuedSMS
from corehq.messaging.smsbackends.start_enterprise.models import StartEnterpriseBackend
from corehq.apps.sms.util import strip_plus
from corehq.messaging.smsbackends.start_enterprise.const import (
    LONG_TEXT_MSG_TYPE,
    LONG_UNICODE_MSG_TYPE,
)
from django.test import TestCase

TEST_USERNAME = 'abc'
TEST_PASSWORD = 'def'
TEST_SENDER_ID = 'ghi'
TEST_PHONE_NUMBER = '+919999999999'
TEST_TEXT_MESSAGE = 'ASCII Message'
TEST_UNICODE_MESSAGE = "\u0928\u092e\u0938\u094d\u0924\u0947"


class TestStartEnterpriseBackendRequest(TestCase):

    def setUp(self):
        self.backend = StartEnterpriseBackend()
        self.backend.set_extra_fields(
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
            sender_id=TEST_SENDER_ID,
        )

    def test_ascii(self):
        queued_sms = QueuedSMS(
            phone_number=TEST_PHONE_NUMBER,
            text=TEST_TEXT_MESSAGE,
        )
        self.assertEqual(
            self.backend.get_params(queued_sms),
            {
                'usr': TEST_USERNAME,
                'pass': TEST_PASSWORD,
                'msisdn': strip_plus(TEST_PHONE_NUMBER),
                'sid': TEST_SENDER_ID,
                'mt': LONG_TEXT_MSG_TYPE,
                'msg': TEST_TEXT_MESSAGE,
            }
        )

    def test_unicode(self):
        queued_sms = QueuedSMS(
            phone_number=TEST_PHONE_NUMBER,
            text=TEST_UNICODE_MESSAGE,
        )
        self.assertEqual(
            self.backend.get_params(queued_sms),
            {
                'usr': TEST_USERNAME,
                'pass': TEST_PASSWORD,
                'msisdn': strip_plus(TEST_PHONE_NUMBER),
                'sid': TEST_SENDER_ID,
                'mt': LONG_UNICODE_MSG_TYPE,
                'msg': '0928092E0938094D09240947',
            }
        )

    def test_phone_number_is_valid(self):
        self.assertFalse(StartEnterpriseBackend.phone_number_is_valid('+91'))
        self.assertFalse(StartEnterpriseBackend.phone_number_is_valid('+123456789'))
        self.assertTrue(StartEnterpriseBackend.phone_number_is_valid('+910123456789'))
