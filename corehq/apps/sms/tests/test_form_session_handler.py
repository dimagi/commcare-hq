from datetime import datetime

from django.test import TestCase
from mock import patch, Mock

from corehq.apps.domain.models import Domain
from corehq.apps.sms.handlers.form_session import form_session_handler
from corehq.apps.sms.models import (
    PhoneNumber,
    SMS,
    INCOMING,
)
from corehq.apps.smsforms.models import SQLXFormsSession


class MockContextManager(object):

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        pass


def mock_critical_section_for_smsforms_sessions(contact_id):
    return MockContextManager()


@patch('corehq.apps.smsforms.util.critical_section_for_smsforms_sessions',
       new=mock_critical_section_for_smsforms_sessions)
class FormSessionTestCase(TestCase):

    def test_open_form_session(self):
        Domain(name='test')
        number = PhoneNumber(
            domain='test',
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
        SQLXFormsSession.create_session_object(
            'test',
            Mock(get_id='contact_id'),
            number.phone_number,
            Mock(get_id='app_id'),
            Mock(xmlns='xmlns'),
            expire_after=24 * 60,
        )
        msg = SMS(
            phone_number=number.phone_number,
            direction=INCOMING,
            date=datetime.utcnow(),
            text="test message",
            domain_scope=None,
            backend_api=None,
            backend_id=None,
            backend_message_id=None,
            raw_text=None,
        )
        form_session_handler(number, msg.text, msg)
        self.assertTrue(msg.messaging_subevent is not None)
