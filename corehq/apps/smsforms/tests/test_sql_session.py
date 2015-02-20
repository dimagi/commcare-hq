from datetime import datetime
import random
import uuid
from couchdbkit import MultipleResultsFound
from django.test import TestCase
from corehq.apps.sms.handlers.form_session import get_single_open_session_or_close_multiple
from corehq.apps.smsforms.models import SQLXFormsSession, XFormsSession, XFORMS_SESSION_TYPES, XFORMS_SESSION_SMS, \
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

    def test_sync_from_creation(self):
        properties = _arbitrary_session_properties()
        couch_session = XFormsSession(**properties)
        couch_session.save()
        sql_session = SQLXFormsSession.objects.get(couch_id=couch_session._id)
        for prop, value in properties.items():
            self.assertEqual(getattr(sql_session, prop), value)

        # make sure we didn't do any excess saves
        self.assertTrue(XFormsSession.get_db().get_rev(couch_session._id).startswith('1-'))

    def test_sync_from_update(self):
        properties = _arbitrary_session_properties()
        couch_session = XFormsSession(**properties)
        couch_session.save()
        sql_session = SQLXFormsSession.objects.get(couch_id=couch_session._id)
        for prop, value in properties.items():
            self.assertEqual(getattr(sql_session, prop), value)

        previous_count = SQLXFormsSession.objects.count()
        updated_properties = _arbitrary_session_properties()
        for attr, val in updated_properties.items():
            couch_session[attr] = val
        couch_session.save()

        # make sure nothing new was created
        self.assertEqual(previous_count, SQLXFormsSession.objects.count())
        # check updated props in the sql model
        sql_session = SQLXFormsSession.objects.get(pk=sql_session.pk)
        for prop, value in updated_properties.items():
            self.assertEqual(getattr(sql_session, prop), value)

    def test_reverse_sync(self):
        properties = _arbitrary_session_properties()
        couch_session = XFormsSession(**properties)
        couch_session.save()
        sql_session = SQLXFormsSession.objects.get(couch_id=couch_session._id)
        for prop, value in properties.items():
            self.assertEqual(getattr(sql_session, prop), value)

        # make sure we didn't do any excess saves
        self.assertTrue(XFormsSession.get_db().get_rev(couch_session._id).startswith('1-'))

        updated_properties = _arbitrary_session_properties()
        for prop, value in updated_properties.items():
            setattr(sql_session, prop, value)
        sql_session.save()

        couch_session = XFormsSession.get(couch_session._id)
        for prop, value in updated_properties.items():
            self.assertEqual(getattr(couch_session, prop), value)
        self.assertTrue(couch_session._rev.startswith('2-'))

    def test_get_all_open_sessions_domain_mismatch(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        _make_session(
            domain='wrong',
            connection_id=contact,
            end_time=None,
            session_type=XFORMS_SESSION_SMS,
        )
        self.assertEqual(0, len(XFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_all_open_sessions_contact_mismatch(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        _make_session(
            domain=domain,
            connection_id='wrong',
            end_time=None,
            session_type=XFORMS_SESSION_SMS,
        )
        self.assertEqual(0, len(XFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_all_open_sessions_already_ended(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        _make_session(
            domain=domain,
            connection_id=contact,
            end_time=datetime.utcnow(),
            session_type=XFORMS_SESSION_SMS,
        )
        self.assertEqual(0, len(XFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_all_open_sessions_wrong_type(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        _make_session(
            domain=domain,
            connection_id=contact,
            end_time=None,
            session_type=XFORMS_SESSION_IVR,
        )
        self.assertEqual(0, len(XFormsSession.get_all_open_sms_sessions(domain, contact)))

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

        couch_sessions = XFormsSession.get_all_open_sms_sessions(domain, contact)
        sql_sessions = SQLXFormsSession.get_all_open_sms_sessions(domain, contact)
        self.assertEqual(3, len(couch_sessions))
        self.assertEqual(3, len(sql_sessions))
        self.assertEqual(set([x._id for x in couch_sessions]), set([x.couch_id for x in sql_sessions]))
        SQLXFormsSession.close_all_open_sms_sessions(domain, contact)
        self.assertEqual(0, len(XFormsSession.get_all_open_sms_sessions(domain, contact)))
        self.assertEqual(0, len(SQLXFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_single_open_session(self):
        properties = _arbitrary_session_properties(
            end_time=None,
            session_type=XFORMS_SESSION_SMS,
        )
        couch_session = XFormsSession(**properties)
        couch_session.save()
        (mult, session) = get_single_open_session_or_close_multiple(
            couch_session.domain, couch_session.connection_id
        )
        self.assertEqual(False, mult)
        self.assertEqual(couch_session._id, session._id)
        [couch_session_back] = XFormsSession.get_all_open_sms_sessions(
            couch_session.domain, couch_session.connection_id
        )
        [sql_session] = SQLXFormsSession.get_all_open_sms_sessions(
            couch_session.domain, couch_session.connection_id
        )
        self.assertEqual(couch_session._id, couch_session_back._id)
        self.assertEqual(couch_session._id, sql_session.couch_id)

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
        self.assertEqual(0, len(XFormsSession.get_all_open_sms_sessions(domain, contact)))
        self.assertEqual(0, len(SQLXFormsSession.get_all_open_sms_sessions(domain, contact)))

    def test_get_open_sms_session_no_results(self):
        for cls in (XFormsSession, SQLXFormsSession):
            self.assertEqual(None, cls.get_open_sms_session(uuid.uuid4().hex, uuid.uuid4().hex))

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

        for cls in (XFormsSession, SQLXFormsSession):
            with self.assertRaises(MultipleResultsFound):
                cls.get_open_sms_session(domain, contact)

    def test_get_open_sms_session_one_result(self):
        domain = uuid.uuid4().hex
        contact = uuid.uuid4().hex
        couch_session = _make_session(
            domain=domain,
            connection_id=contact,
            end_time=None,
            session_type=XFORMS_SESSION_SMS,
        )
        for cls in (XFormsSession, SQLXFormsSession):
            session = cls.get_open_sms_session(domain, contact)
            self.assertEqual(couch_session.session_id, session.session_id)


def _make_session(**kwargs):
    properties = _arbitrary_session_properties(**kwargs)
    couch_session = XFormsSession(**properties)
    couch_session.save()
    return couch_session


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
