import contextlib
import uuid
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

from django.test import TestCase

from corehq.apps.sms.handlers.form_session import form_session_handler
from corehq.apps.sms.models import (
    INCOMING,
    SMS,
    PhoneNumber,
)
from corehq.apps.smsforms.models import (
    SQLXFormsSession,
    XFormsSessionSynchronization,
    get_channel_for_contact,
)
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.util.test_utils import flag_enabled


@flag_enabled("ONE_PHONE_NUMBER_MULTIPLE_CONTACTS")
@patch('corehq.apps.smsforms.util.critical_section_for_smsforms_sessions',
       new=lambda contact_id: contextlib.supress())
class FormSessionMultipleContactsTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.domain_name1 = uuid.uuid4().hex
        cls.domain_name2 = uuid.uuid4().hex

        cls.backend = SQLTestSMSBackend.objects.create(
            name='BACKEND',
            domain=cls.domain_name1,
            is_global=False,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

        cls.number1 = PhoneNumber.objects.create(
            domain=cls.domain_name1,
            owner_doc_type='CommCareCase',
            owner_id='fake-owner-id1',
            phone_number='01112223333',
            backend_id='BACKEND',
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
            phone_number='01112223333',
            backend_id='BACKEND',
            ivr_backend_id=None,
            verified=True,
            is_two_way=True,
            pending_verification=False,
            contact_last_modified=datetime.utcnow()
        )

    def setUp(self):
        get_channel_for_contact.clear(self.number1.owner_id, self.number1.phone_number)
        get_channel_for_contact.clear(self.number2.owner_id, self.number2.phone_number)

    @patch('corehq.apps.sms.handlers.form_session.answer_next_question', MagicMock(return_value=None))
    def test_incoming_sms_linked_form_session__session_contact_matches_incoming(self):
        session = self._make_session(self.number1)
        self._claim_channel(session)

        msg = self._get_sms1()
        handled = form_session_handler(self.number1, msg.text, msg)
        self.assertTrue(handled)

        # message gets attached to the correct session
        self.assertEqual(msg.xforms_session_couch_id, session.couch_id)

        # sticky session is still 'open'
        session_info = XFormsSessionSynchronization.get_running_session_info_for_channel(session.get_channel())

        self.assertEqual(session_info.session_id, session.session_id)
        self.assertEqual(session_info.contact_id, session.connection_id)

        # complete and close session
        session.mark_completed(True)
        session.close()

        # confirm session closed
        self.assertFalse(session.session_is_open)
        self.assertTrue(session.completed)

    @patch('corehq.apps.sms.handlers.form_session.answer_next_question', MagicMock(return_value=None))
    @patch('corehq.apps.sms.handlers.form_session.send_sms_to_verified_number', MagicMock(return_value=None))
    def test_incoming_sms_linked_form_session__session_contact_different_from_incoming(self):
        session = self._make_session(self.number2)
        self._claim_channel(session)

        msg = self._get_sms2()
        # session belongs to `number2` but message comes from `number1` NOT THE CASE ANY MORE
        handled = form_session_handler(self.number2, msg.text, msg)
        self.assertTrue(handled)

        session.refresh_from_db()
        self.assertTrue(session.session_is_open)
        self.assertFalse(session.completed)

        # sticky session is removed
        session_info = XFormsSessionSynchronization.get_running_session_info_for_channel(session.get_channel())
        self.assertEqual(session_info.session_id, session.session_id)
        self.assertEqual(session_info.contact_id, session.connection_id)

    def _claim_channel(self, session):
        XFormsSessionSynchronization.claim_channel_for_session(session)
        self.addCleanup(XFormsSessionSynchronization.release_channel_for_session, session)

    def _make_session(self, number):
        session = SQLXFormsSession.create_session_object(
            self.domain_name1,
            Mock(get_id=number.owner_id),
            number.phone_number,
            Mock(get_id='app_id'),
            Mock(xmlns='xmlns'),
            expire_after=24 * 60,
        )
        session.session_id = uuid.uuid4().hex
        session.save()
        return session

    def _get_sms1(self):
        msg = SMS(
            phone_number=self.number1.phone_number,
            direction=INCOMING,
            date=datetime.utcnow(),
            text="test message",
            domain_scope=None,
            backend_api=None,
            backend_id=None,
            backend_message_id=None,
            raw_text=None,
        )
        return msg

    def _get_sms2(self):
        msg = SMS(
            phone_number=self.number2.phone_number,
            direction=INCOMING,
            date=datetime.utcnow(),
            text="test message",
            domain_scope=None,
            backend_api=None,
            backend_id=None,
            backend_message_id=None,
            raw_text=None,
        )
        return msg
