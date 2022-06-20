import contextlib
import uuid
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase

from corehq.apps.formplayer_api.smsforms.tests.test_formplayer_interface import (
    MockFormplayerRequest,
)
from corehq.apps.sms.api import _process_incoming
from corehq.apps.sms.models import (
    INCOMING,
    SMS,
    MobileBackendInvitation,
    PhoneNumber,
    SQLMobileBackendMapping,
)
from corehq.apps.smsforms.models import (
    SMSChannel,
    SQLXFormsSession,
    XFormsSessionSynchronization,
    get_channel_for_contact,
)
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.util.test_utils import flag_enabled

QUESTION_RESPONSE = {
    "event": {
        "datatype": "text",
        "choices": None,
        "caption": "Name",
        "type": "question",
        "answer": None,
        "required": 0,
        "ix": "1",
        "help": None
    }
}

ANSWER_RESPONSE = {
    "event": {
        "datatype": None,
        "choices": None,
        "caption": None,
        "type": "form-complete",
        "answer": None,
        "required": 0,
        "ix": "1",
        "help": None,
        "output": "<xml>dummy form xml</xml>"
    }
}


@flag_enabled("ONE_PHONE_NUMBER_MULTIPLE_CONTACTS")
@flag_enabled("INBOUND_SMS_LENIENCY")
@patch('corehq.apps.smsforms.util.critical_section_for_smsforms_sessions',
       new=lambda contact_id: contextlib.nullcontext())
@patch('corehq.apps.sms.api.get_location_id_by_verified_number', MagicMock(return_value=None))
@patch('corehq.apps.sms.api._domain_accepts_inbound', MagicMock(return_value=True))
@patch('corehq.apps.sms.api.domain_has_privilege', MagicMock(return_value=True))
@patch('corehq.apps.sms.api._allow_load_handlers', MagicMock(return_value=True))
@patch('corehq.apps.smsforms.util.submit_form_locally', MagicMock(
    return_value=Mock(xform=Mock(form_id="123"))))
class FormSessionMultipleContactsTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.domain_name1 = "domain1"
        cls.domain_name2 = "domain2"

        cls.backend = SQLTestSMSBackend.objects.create(
            name='BACKEND',
            domain=cls.domain_name1,
            is_global=False,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        # share the backend with the 2nd domain
        MobileBackendInvitation.objects.create(domain=cls.domain_name2, backend=cls.backend, accepted=True)

        # set up the backend mapping
        SQLMobileBackendMapping.set_default_domain_backend(cls.domain_name1, cls.backend)
        SQLMobileBackendMapping.set_default_domain_backend(cls.domain_name2, cls.backend)

        cls.phone_number = '01112223333'
        cls.number1 = PhoneNumber.objects.create(
            domain=cls.domain_name1,
            owner_doc_type='CommCareCase',
            owner_id='fake-owner-id1',
            phone_number=cls.phone_number,
            backend_id=None,
            ivr_backend_id=None,
            verified=True,
            is_two_way=True,
            pending_verification=False,
            contact_last_modified=datetime.utcnow()
        )

        cls.number2 = PhoneNumber.objects.create(
            domain=cls.domain_name2,
            owner_doc_type='CommCareCase',
            owner_id='fake-owner-id2',
            phone_number=cls.phone_number,
            backend_id=None,
            ivr_backend_id=None,
            verified=True,
            is_two_way=False,
            pending_verification=False,
            contact_last_modified=datetime.utcnow()
        )

    def setUp(self):
        get_channel_for_contact.clear(self.number1.owner_id, self.number1.phone_number)
        get_channel_for_contact.clear(self.number2.owner_id, self.number2.phone_number)
        SQLMobileBackendMapping.get_prefix_to_backend_map.clear("SMS", None)
        SQLMobileBackendMapping.get_prefix_to_backend_map.clear("SMS", self.domain_name1)
        SQLMobileBackendMapping.get_prefix_to_backend_map.clear("SMS", self.domain_name2)

    def test_sms_form_session_in_primary_domain_with_plus_prefix(self):
        self._test(self.number1, with_prefix=True)

    def test_sms_form_session_in_primary_domain_without_plus_prefix(self):
        self._test(self.number1, with_prefix=False)

    def test_sms_form_session_in_secondary_domain_with_plus_prefix(self):
        self._test(self.number2, with_prefix=True)

    def test_sms_form_session_in_secondary_domain_without_plus_prefix(self):
        self._test(self.number2, with_prefix=False)

    def _test(self, number, with_prefix):
        session = self._make_session(number)
        self._claim_channel(session)

        channel = session.get_channel()

        mocker = MockFormplayerRequest("current", QUESTION_RESPONSE)
        mocker.add_action("answer", ANSWER_RESPONSE)
        sms_number = number.phone_number
        if with_prefix:
            sms_number = "+" + sms_number
        msg = self._get_sms(sms_number)
        with mocker:
            # with the mocks configured this should result in the session being completed
            _process_incoming(msg)

        # message gets attached to the correct session
        self.assertEqual(msg.xforms_session_couch_id, session.couch_id)

        # confirm session closed
        session.refresh_from_db()
        self.assertFalse(session.session_is_open)
        self.assertTrue(session.completed)
        self.assertEqual(session.submission_id, "123")

        # sticky session is released
        session_info = XFormsSessionSynchronization.get_running_session_info_for_channel(channel)

        self.assertIsNone(session_info.session_id)
        self.assertEqual(session_info.contact_id, session.connection_id)

    def _claim_channel(self, session):
        self.assertEqual(session.get_channel(), SMSChannel(
            backend_id=self.backend.couch_id, phone_number=self.phone_number))

        self.assertTrue(XFormsSessionSynchronization.channel_is_available_for_session(session))
        XFormsSessionSynchronization.claim_channel_for_session(session)

    def _make_session(self, number):
        session = SQLXFormsSession.create_session_object(
            number.domain,
            Mock(get_id=number.owner_id),
            number.phone_number,
            Mock(get_id='app_id'),
            Mock(xmlns='xmlns'),
            expire_after=24 * 60,
        )
        session.session_id = uuid.uuid4().hex
        session.save()
        return session

    def _get_sms(self, phone_number):
        msg = SMS(
            phone_number=phone_number,
            direction=INCOMING,
            date=datetime.utcnow(),
            text="test message",
            domain_scope=self.backend.domain,
            backend_api=self.backend.get_api_id(),
            backend_id=self.backend.couch_id,
            backend_message_id=None,
        )
        return msg
