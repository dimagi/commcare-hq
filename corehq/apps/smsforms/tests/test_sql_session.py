from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
import random
import uuid
from couchdbkit import MultipleResultsFound
from django.test import TestCase
from corehq.apps.sms.handlers.form_session import get_single_open_session_or_close_multiple
from corehq.apps.smsforms.models import SQLXFormsSession, XFORMS_SESSION_TYPES, XFORMS_SESSION_SMS, \
    XFORMS_SESSION_IVR
from mock import patch, Mock
from six.moves import range


class SQLSessionTestCase(TestCase):

    def test_get_by_session_id(self):
        sql_session = _make_session()
        self.assertEqual(sql_session.pk, SQLXFormsSession.by_session_id(sql_session.session_id).pk)

    def test_get_by_session_id_not_found(self):
        self.assertEqual(None, SQLXFormsSession.by_session_id(uuid.uuid4().hex))

    def test_get_all_open_sessions_domain_mismatch(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        _make_session(
            domain='wrong',
            connection_id=contact,
            end_time=None,
            session_is_open=True,
            session_type=XFORMS_SESSION_SMS,
        )
        self.assertEqual(0, len(SQLXFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_all_open_sessions_contact_mismatch(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        _make_session(
            domain=domain,
            connection_id='wrong',
            end_time=None,
            session_is_open=True,
            session_type=XFORMS_SESSION_SMS,
        )
        self.assertEqual(0, len(SQLXFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_all_open_sessions_already_ended(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        _make_session(
            domain=domain,
            connection_id=contact,
            end_time=datetime.utcnow(),
            session_is_open=False,
            session_type=XFORMS_SESSION_SMS,
        )
        self.assertEqual(0, len(SQLXFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_all_open_sessions_wrong_type(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        _make_session(
            domain=domain,
            connection_id=contact,
            end_time=None,
            session_is_open=True,
            session_type=XFORMS_SESSION_IVR,
        )
        self.assertEqual(0, len(SQLXFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_and_close_all_open_sessions(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        for i in range(3):
            _make_session(
                domain=domain,
                connection_id=contact,
                end_time=None,
                session_is_open=True,
                session_type=XFORMS_SESSION_SMS,
            )

        sql_sessions = SQLXFormsSession.get_all_open_sms_sessions(domain, contact)
        self.assertEqual(3, len(sql_sessions))
        SQLXFormsSession.close_all_open_sms_sessions(domain, contact)
        self.assertEqual(0, len(SQLXFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_single_open_session(self):
        properties = _arbitrary_session_properties(
            end_time=None,
            session_is_open=True,
            session_type=XFORMS_SESSION_SMS,
        )
        session = SQLXFormsSession(**properties)
        session.save()
        (mult, session) = get_single_open_session_or_close_multiple(
            session.domain, session.connection_id
        )
        self.assertEqual(False, mult)
        [session_back] = SQLXFormsSession.get_all_open_sms_sessions(
            session.domain, session.connection_id
        )
        self.assertEqual(session._id, session_back.couch_id)

    def test_get_single_open_session_close_multiple(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        for i in range(3):
            _make_session(
                domain=domain,
                connection_id=contact,
                end_time=None,
                session_is_open=True,
                session_type=XFORMS_SESSION_SMS,
            )

        (mult, session) = get_single_open_session_or_close_multiple(domain, contact)
        self.assertEqual(True, mult)
        self.assertEqual(None, session)
        self.assertEqual(0, len(SQLXFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_open_sms_session_no_results(self):
        self.assertEqual(None, SQLXFormsSession.get_open_sms_session(uuid.uuid4().hex, uuid.uuid4().hex))

    def test_get_open_sms_session_multiple_results(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        for i in range(3):
            _make_session(
                domain=domain,
                connection_id=contact,
                end_time=None,
                session_is_open=True,
                session_type=XFORMS_SESSION_SMS,
            )

        with self.assertRaises(MultipleResultsFound):
            SQLXFormsSession.get_open_sms_session(domain, contact)

    def test_get_open_sms_session_one_result(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        new_session = _make_session(
            domain=domain,
            connection_id=contact,
            end_time=None,
            session_is_open=True,
            session_type=XFORMS_SESSION_SMS,
        )

        session = SQLXFormsSession.get_open_sms_session(domain, contact)
        self.assertEqual(new_session.session_id, session.session_id)

    @patch('corehq.apps.smsforms.models.utcnow')
    def test_move_to_next_action_with_no_reminders(self, utcnow_mock):
        utcnow_mock.return_value = datetime(2018, 1, 1, 0, 0)
        session = SQLXFormsSession.create_session_object(
            'test',
            Mock(get_id='contact_id'),
            '+9990001',
            Mock(get_id='app_id'),
            Mock(xmlns='xmlns'),
            expire_after=24 * 60,
        )
        self.assertTrue(session.session_is_open)
        self.assertEqual(session.start_time, datetime(2018, 1, 1, 0, 0))
        self.assertIsNone(session.end_time)
        self.assertEqual(session.current_action_due, datetime(2018, 1, 2, 0, 0))
        self.assertFalse(session.current_action_is_a_reminder)

        utcnow_mock.return_value = datetime(2018, 1, 2, 0, 1)
        session.move_to_next_action()
        self.assertTrue(session.session_is_open)
        self.assertEqual(session.start_time, datetime(2018, 1, 1, 0, 0))
        self.assertIsNone(session.end_time)
        self.assertEqual(session.current_action_due, datetime(2018, 1, 2, 0, 0))
        self.assertFalse(session.current_action_is_a_reminder)

    @patch('corehq.apps.smsforms.models.utcnow')
    def test_move_to_next_action_with_reminders(self, utcnow_mock):
        utcnow_mock.return_value = datetime(2018, 1, 1, 0, 0)
        session = SQLXFormsSession.create_session_object(
            'test',
            Mock(get_id='contact_id'),
            '+9990001',
            Mock(get_id='app_id'),
            Mock(xmlns='xmlns'),
            expire_after=24 * 60,
            reminder_intervals=[30, 60]
        )
        self.assertTrue(session.session_is_open)
        self.assertEqual(session.start_time, datetime(2018, 1, 1, 0, 0))
        self.assertIsNone(session.end_time)
        self.assertEqual(session.current_action_due, datetime(2018, 1, 1, 0, 30))
        self.assertTrue(session.current_action_is_a_reminder)

        utcnow_mock.return_value = datetime(2018, 1, 1, 0, 31)
        session.move_to_next_action()
        self.assertTrue(session.session_is_open)
        self.assertEqual(session.start_time, datetime(2018, 1, 1, 0, 0))
        self.assertIsNone(session.end_time)
        self.assertEqual(session.current_action_due, datetime(2018, 1, 1, 1, 30))
        self.assertTrue(session.current_action_is_a_reminder)

        utcnow_mock.return_value = datetime(2018, 1, 1, 1, 31)
        session.move_to_next_action()
        self.assertTrue(session.session_is_open)
        self.assertEqual(session.start_time, datetime(2018, 1, 1, 0, 0))
        self.assertIsNone(session.end_time)
        self.assertEqual(session.current_action_due, datetime(2018, 1, 2, 0, 0))
        self.assertFalse(session.current_action_is_a_reminder)

        utcnow_mock.return_value = datetime(2018, 1, 2, 0, 1)
        session.move_to_next_action()
        self.assertTrue(session.session_is_open)
        self.assertEqual(session.start_time, datetime(2018, 1, 1, 0, 0))
        self.assertIsNone(session.end_time)
        self.assertEqual(session.current_action_due, datetime(2018, 1, 2, 0, 0))
        self.assertFalse(session.current_action_is_a_reminder)

    @patch('corehq.apps.smsforms.models.utcnow')
    def test_move_to_next_action_with_fast_forwarding(self, utcnow_mock):
        utcnow_mock.return_value = datetime(2018, 1, 1, 0, 0)
        session = SQLXFormsSession.create_session_object(
            'test',
            Mock(get_id='contact_id'),
            '+9990001',
            Mock(get_id='app_id'),
            Mock(xmlns='xmlns'),
            expire_after=24 * 60,
            reminder_intervals=[30, 60]
        )
        self.assertTrue(session.session_is_open)
        self.assertEqual(session.start_time, datetime(2018, 1, 1, 0, 0))
        self.assertIsNone(session.end_time)
        self.assertEqual(session.current_action_due, datetime(2018, 1, 1, 0, 30))
        self.assertTrue(session.current_action_is_a_reminder)

        utcnow_mock.return_value = datetime(2018, 1, 3, 0, 0)
        session.move_to_next_action()
        self.assertTrue(session.session_is_open)
        self.assertEqual(session.start_time, datetime(2018, 1, 1, 0, 0))
        self.assertIsNone(session.end_time)
        self.assertEqual(session.current_action_due, datetime(2018, 1, 2, 0, 0))
        self.assertFalse(session.current_action_is_a_reminder)


def _make_session(**kwargs):
    properties = _arbitrary_session_properties(**kwargs)
    session = SQLXFormsSession(**properties)
    session.save()
    return session


def _arbitrary_session_properties(**kwargs):
    def arbitrary_string(max_len=32):
        return uuid.uuid4().hex[:max_len]

    def arbitrary_date():
        return datetime(
            random.choice(list(range(2010, 2015))),
            random.choice(list(range(1, 13))),
            random.choice(list(range(1, 28))),
        )

    def arbitrary_bool():
        return random.choice([True, False])

    def arbitrary_int(min_value, max_value):
        return random.randint(min_value, max_value)

    properties = {
        'connection_id': arbitrary_string(),
        'session_id': arbitrary_string(),
        'form_xmlns': arbitrary_string(),
        'start_time': arbitrary_date(),
        'modified_time': arbitrary_date(),
        'end_time': arbitrary_date(),
        'completed': arbitrary_bool(),
        'domain': arbitrary_string(),
        'user_id': arbitrary_string(),
        'app_id': arbitrary_string(),
        'submission_id': arbitrary_string(),
        'survey_incentive': arbitrary_string(),
        'session_type': random.choice(XFORMS_SESSION_TYPES),
        'workflow': arbitrary_string(20),
        'reminder_id': arbitrary_string(),
        'phone_number': arbitrary_string(10),
        'expire_after': arbitrary_int(60, 1000),
        'session_is_open': False,
        'reminder_intervals': [],
        'current_reminder_num': 0,
        'current_action_due': arbitrary_date(),
        'submit_partially_completed_forms': False,
        'include_case_updates_in_partial_submissions': False,
    }
    properties.update(kwargs)
    return properties
