from datetime import datetime
import random
import uuid
from couchdbkit import MultipleResultsFound
from django.test import TestCase
from corehq.apps.sms.handlers.form_session import get_single_open_session_or_close_multiple
from corehq.apps.smsforms.models import SQLXFormsSession, XFORMS_SESSION_TYPES, XFORMS_SESSION_SMS, \
    XFORMS_SESSION_IVR


class SQLSessionTestCase(TestCase):

    def test_get_by_session_id(self):
        session_id = uuid.uuid4().hex
        sql_session = SQLXFormsSession.objects.create(
            session_id=session_id,
            start_time=datetime.utcnow(),
            modified_time=datetime.utcnow(),
        )
        self.assertEqual(sql_session.pk, SQLXFormsSession.by_session_id(session_id).pk)

    def test_get_by_session_id_not_found(self):
        self.assertEqual(None, SQLXFormsSession.by_session_id(uuid.uuid4().hex))

    def test_get_all_open_sessions_domain_mismatch(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        _make_session(
            domain='wrong',
            connection_id=contact,
            end_time=None,
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
                session_type=XFORMS_SESSION_SMS,
            )

        sql_sessions = SQLXFormsSession.get_all_open_sms_sessions(domain, contact)
        self.assertEqual(3, len(sql_sessions))
        SQLXFormsSession.close_all_open_sms_sessions(domain, contact)
        self.assertEqual(0, len(SQLXFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_single_open_session(self):
        properties = _arbitrary_session_properties(
            end_time=None,
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
            session_type=XFORMS_SESSION_SMS,
        )

        session = SQLXFormsSession.get_open_sms_session(domain, contact)
        self.assertEqual(new_session.session_id, session.session_id)


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
            random.choice(range(2010, 2015)),
            random.choice(range(1, 13)),
            random.choice(range(1, 28)),
        )

    def arbitrary_bool():
        return random.choice([True, False])

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
    }
    properties.update(kwargs)
    return properties
