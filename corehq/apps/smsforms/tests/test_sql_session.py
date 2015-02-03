from datetime import datetime
import random
import uuid
from django.test import TestCase
from corehq.apps.smsforms.models import SQLXFormsSession, XFormsSession, XFORMS_SESSION_TYPES


class SQLSessionTestCase(TestCase):

    def test_sync(self):
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
        couch_session = XFormsSession(**properties)
        couch_session.save()

        sql_session = SQLXFormsSession.objects.get(couch_id=couch_session._id)

        for prop, value in properties.items():
            self.assertEqual(getattr(sql_session, prop), value)
