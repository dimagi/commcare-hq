from django.test import TestCase
from datetime import datetime

from corehq.apps.events.models import Event, NOT_STARTED
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser


class TestEventModel(TestCase):

    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.webuser = WebUser.create(
            cls.domain,
            'funky-user',
            'mockmock',
            None,
            None
        )
        cls.webuser.save()

    @classmethod
    def tearDownClass(cls):
        cls.webuser.delete(None, None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_create_event(self):
        now = datetime.utcnow().date()

        event_data = {
            'domain': self.domain,
            'name': 'test-event',
            'start_date': now,
            'end_date': now,
            'attendance_target': 10,
            'sameday_reg': True,
            'track_each_day': False,
            'manager_id': self.webuser.user_id,
        }
        event = Event(**event_data)
        event.save()

        self.assertEqual(event.status, NOT_STARTED)
        self.assertEqual(event.is_open, True)
        self.assertTrue(event.event_id is not None)
