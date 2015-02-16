from datetime import datetime
import random
import uuid
from django.test import TestCase
from corehq.apps.smsforms.models import SQLXFormsSession, XFormsSession, XFORMS_SESSION_TYPES


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


def _arbitrary_session_properties():
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

    return {
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
