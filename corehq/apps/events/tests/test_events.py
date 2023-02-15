from django.test import TestCase
from datetime import datetime

from corehq.apps.events.models import (
    Event,
    EVENT_CASE_TYPE,
)
from corehq.form_processor.tests.utils import create_case
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import CommCareCase


class TestEventLogic(TestCase):

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

    def test_get_obj_from_data(self):
        now = datetime.utcnow().date()

        event_data = {
            'domain': self.domain,
            'name': 'test-event',
            'start_date': now,
            'end_date': now,
            'attendance_target': 10,
            'sameday_reg': True,
            'track_each_day': False,
            'manager': None,
        }
        event = Event.get_obj_from_data(event_data)

        self.assertTrue(isinstance(event, Event))

        self.assertTrue(event.domain == self.domain)
        self.assertTrue(event.name == 'test-event')
        self.assertTrue(event.start_date == now)
        self.assertTrue(event.end_date == now)
        self.assertTrue(event.attendance_target == 10)
        self.assertTrue(event.sameday_reg is True)
        self.assertFalse(event.track_each_day)
        self.assertFalse(hasattr(event, 'case'))
        self.assertTrue(event.manager is None)
        self.assertTrue(event.is_open == Event.is_open)
        self.assertTrue(event.attendee_list_status == Event.attendee_list_status)

    def test_get_obj_from_case(self):
        now = datetime.utcnow().date()
        case_args = {
            'name': 'test-event',
            'case_json': {
                'start_date': now,
                'end_date': now,
                'attendance_target': 10,
                'sameday_reg': True,
                'track_each_day': False,
                'is_open': False,
                'attendee_list_status': 'Accepted'
            }
        }
        case_ = create_case(
            self.domain,
            case_type=EVENT_CASE_TYPE,
            user_id=self.webuser.user_id,
            **case_args,
        )
        event = Event.get_obj_from_case(case_)

        self.assertTrue(isinstance(event, Event))
        self.assertTrue(event.case == case_)
        self.assertFalse(event.is_open)
        self.assertTrue(event.attendee_list_status == 'Accepted')

    def test_event_save_creates_case(self):
        now = datetime.utcnow().date()

        event_data = {
            'domain': self.domain,
            'name': 'test-event',
            'start_date': now,
            'end_date': now,
            'attendance_target': 10,
            'sameday_reg': True,
            'track_each_day': False,
            'manager': self.webuser,
        }
        event = Event.get_obj_from_data(event_data)
        self.assertFalse(hasattr(event, 'case'))
        # A case will be created if the event does not have a case associated with it

        event.save()
        self.assertTrue(hasattr(event, 'case'))

        case_ = event.case
        self.assertTrue(isinstance(case_, CommCareCase))
        self.assertTrue(case_.case_id == event.event_id)
        self.assertTrue(case_.type == EVENT_CASE_TYPE)
