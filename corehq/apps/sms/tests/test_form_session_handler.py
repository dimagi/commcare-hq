import contextlib
from datetime import datetime
import uuid

from django.test import TestCase
from unittest.mock import patch, Mock, MagicMock

from corehq.apps.domain.models import Domain
from corehq.apps.sms.handlers.form_session import form_session_handler
from corehq.apps.sms.models import (
    PhoneNumber,
    SMS,
    INCOMING,
    MessagingEvent,
    MessagingSubEvent
)
from corehq.apps.smsforms.models import SQLXFormsSession
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend


@patch('corehq.apps.smsforms.util.critical_section_for_smsforms_sessions',
       new=lambda contact_id: contextlib.supress())
class FormSessionTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = Domain(name=uuid.uuid4().hex)
        cls.domain.save()

        cls.number = PhoneNumber(
            domain=cls.domain.name,
            owner_doc_type='CommCareCase',
            owner_id='fake-owner-id1',
            phone_number='01112223333',
            backend_id=None,
            ivr_backend_id=None,
            verified=True,
            is_two_way=True,
            pending_verification=False,
            contact_last_modified=datetime.utcnow()
        )
        cls.number.save()

        cls.session = SQLXFormsSession.create_session_object(
            cls.domain.name,
            Mock(get_id=cls.number.owner_id),
            cls.number.phone_number,
            Mock(get_id='app_id'),
            Mock(xmlns='xmlns'),
            expire_after=24 * 60,
        )
        cls.session.save()

        cls.backend = SQLTestSMSBackend.objects.create(
            name='BACKEND',
            domain=cls.domain,
            is_global=False,
            hq_api_id=SQLTestSMSBackend.get_api_id()
        )

    @classmethod
    def tearDownClass(cls):
        cls.number.delete()
        cls.backend.delete()
        cls.session.delete()
        cls.domain.delete()
        super().tearDownClass()

    def _create_message_event_and_subevent(self):
        event = MessagingEvent.objects.create(
            domain=self.domain.name,
            date=datetime.utcnow(),
            source=MessagingEvent.SOURCE_BROADCAST,
            content_type=MessagingEvent.CONTENT_SMS_SURVEY,
            status=MessagingEvent.STATUS_COMPLETED
        )
        subevent = MessagingSubEvent.objects.create(
            parent=event,
            date=datetime.utcnow(),
            recipient_type=MessagingEvent.RECIPIENT_CASE,
            content_type=MessagingEvent.CONTENT_SMS_SURVEY,
            status=MessagingEvent.STATUS_IN_PROGRESS,
            xforms_session=self.session
        )
        self.addCleanup(event.delete)  # cascades to subevent

        return event, subevent

    @patch('corehq.apps.sms.handlers.form_session.answer_next_question', MagicMock(return_value=None))
    def test_incoming_sms_linked_form_session(self):
        event, expected_subevent = self._create_message_event_and_subevent()
        msg = SMS(
            phone_number=self.number.phone_number,
            direction=INCOMING,
            date=datetime.utcnow(),
            text="test message",
            domain_scope=None,
            backend_api=None,
            backend_id=None,
            backend_message_id=None,
            raw_text=None,
        )
        self.addCleanup(msg.delete)

        form_session_handler(self.number, msg.text, msg)

        self.assertEqual(expected_subevent, msg.messaging_subevent)

    @patch('corehq.apps.sms.handlers.form_session.answer_next_question', MagicMock(return_value=None))
    def test_incoming_sms_not_linked_form_session(self):
        # no message event or subevent exist
        msg = SMS(
            phone_number=self.number.phone_number,
            direction=INCOMING,
            date=datetime.utcnow(),
            text="test message",
            domain_scope=None,
            backend_api=None,
            backend_id=None,
            backend_message_id=None,
            raw_text=None,
        )
        self.addCleanup(msg.delete)

        form_session_handler(self.number, msg.text, msg)

        self.assertEqual(msg.messaging_subevent, None)

    @patch('corehq.apps.sms.handlers.form_session.answer_next_question', MagicMock(return_value=None))
    def test_incoming_sms_multiple_subevents_for_session(self):
        first_event, first_subevent = self._create_message_event_and_subevent()
        second_event, second_subevent = self._create_message_event_and_subevent()

        # no message event or subevent exist
        msg = SMS(
            phone_number=self.number.phone_number,
            direction=INCOMING,
            date=datetime.utcnow(),
            text="test message",
            domain_scope=None,
            backend_api=None,
            backend_id=None,
            backend_message_id=None,
            raw_text=None,
        )
        self.addCleanup(msg.delete)

        form_session_handler(self.number, msg.text, msg)

        # assert that the most recent subevent is used
        self.assertNotEqual(first_subevent, msg.messaging_subevent)
        self.assertEqual(second_subevent, msg.messaging_subevent)
