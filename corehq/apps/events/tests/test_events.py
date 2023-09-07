from datetime import datetime, timedelta

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser

from ..models import (
    ATTENDEE_LIST_UNDER_REVIEW,
    EVENT_IN_PROGRESS,
    EVENT_NOT_STARTED,
    Event,
)


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

        event = self._create_event(start_date=now, end_date=now)

        self.assertEqual(event.status, EVENT_IN_PROGRESS)
        self.assertEqual(event.is_open, True)
        self.assertTrue(event.event_id is not None)

    def test_event_status_set_correctly(self):
        now = datetime.utcnow()
        today = now.date()

        yesterday = (now - timedelta(days=1)).date()
        tomorrow = (now + timedelta(days=1)).date()
        two_days_from_now = (now + timedelta(days=2)).date()

        not_started_event = self._create_event(start_date=tomorrow, end_date=two_days_from_now)
        in_progress_event1 = self._create_event(start_date=yesterday, end_date=tomorrow)
        in_progress_event2 = self._create_event(start_date=today, end_date=tomorrow)
        under_review_event = self._create_event(start_date=yesterday, end_date=yesterday)

        self.assertTrue(not_started_event.status, EVENT_NOT_STARTED)
        self.assertTrue(in_progress_event1.status, EVENT_IN_PROGRESS)
        self.assertTrue(in_progress_event2.status, EVENT_IN_PROGRESS)
        self.assertTrue(under_review_event.status, ATTENDEE_LIST_UNDER_REVIEW)
        self.assertTrue(under_review_event.attendee_list_status, ATTENDEE_LIST_UNDER_REVIEW)

    def _create_event(self, start_date, end_date):
        event_data = {
            'domain': self.domain,
            'name': 'test-event',
            'start_date': start_date,
            'end_date': end_date,
            'attendance_target': 10,
            'sameday_reg': True,
            'track_each_day': False,
            'manager_id': self.webuser.user_id,
        }
        event = Event(**event_data)
        event.save()
        return event
