import doctest
from contextlib import contextmanager
from datetime import datetime

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.events.exceptions import InvalidAttendee
from corehq.apps.events.models import (
    ATTENDEE_CASE_TYPE,
    NOT_STARTED,
    Attendee,
    AttendeeCase,
    Event,
)
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.util.test_utils import create_test_case

DOMAIN = 'test-domain'


class TestAttendeeCaseManager(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = CaseFactory(DOMAIN)

    @contextmanager
    def get_attendee_cases(self):
        with create_test_case(
            DOMAIN,
            ATTENDEE_CASE_TYPE,
            'Oliver Opencase',
        ) as open_case, create_test_case(
            DOMAIN,
            ATTENDEE_CASE_TYPE,
            'Clarence Closedcase',
        ) as closed_case:
            self.factory.close_case(closed_case.case_id)
            yield open_case, closed_case

    def test_manager_returns_open_cases(self):
        with self.get_attendee_cases() as (open_case, closed_case):
            cases = AttendeeCase.objects.by_domain(DOMAIN)
            self.assertEqual(cases, [open_case])


class TestAttendee(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        for attendee in Attendee.objects.by_domain(DOMAIN):
            attendee.delete()
        super().tearDownClass()

    def test_save_fails_without_user_id(self):
        try:
            Attendee(domain='bogus').save(user_id=None)
            self.assertTrue(False)
        except InvalidAttendee:
            self.assertTrue(True)

    def test_case_created_on_attendee_save(self):
        mobile_worker = create_mobile_worker('iworkmobiles', DOMAIN)
        domain_attendees = Attendee.objects.by_domain(DOMAIN)
        self.assertEqual(list(domain_attendees), [])

        attendee = Attendee(domain=DOMAIN)
        attendee.save(mobile_worker.user_id)

        domain_attendees = Attendee.objects.by_domain(DOMAIN)
        self.assertTrue(len(domain_attendees) == 1)
        self.assertTrue(domain_attendees[0].case_id is not None)

        attendee_case = CommCareCase.objects.get_case(domain_attendees[0].case_id, DOMAIN)
        self.assertEqual(attendee_case.name, mobile_worker.username)
        self.assertEqual(attendee_case.get_case_property('commcare_user_id'), mobile_worker.user_id)

    def test_case_deleted_on_attendee_delete(self):
        mobile_worker = create_mobile_worker('delete_me', DOMAIN)
        domain_attendees = Attendee.objects.by_domain(DOMAIN)
        self.assertEqual(list(domain_attendees), [])

        attendee = Attendee(domain=DOMAIN)
        attendee.save(mobile_worker.user_id)

        domain_attendees = Attendee.objects.by_domain(DOMAIN)
        case_id = domain_attendees[0].case_id
        attendee_case = CommCareCase.objects.get_case(case_id, DOMAIN)
        self.assertTrue(attendee_case is not None)
        self.assertTrue(attendee_case.deleted is False)

        attendee.delete()
        self.assertEqual(list(Attendee.objects.by_domain(DOMAIN)), [])
        attendee_case = CommCareCase.objects.get_case(case_id, DOMAIN)
        self.assertTrue(attendee_case.deleted is True)


class TestEventModel(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.webuser = WebUser.create(
            DOMAIN,
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
        for attendee in Attendee.objects.by_domain(DOMAIN):
            attendee.delete()
        super().tearDownClass()

    def test_create_event(self):
        now = datetime.utcnow().date()

        event_data = {
            'domain': DOMAIN,
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

    def test_create_event_with_attendees(self):
        now = datetime.utcnow().date()

        attendee = self._create_attendee_on_domain('signmeup')

        event_data = {
            'domain': DOMAIN,
            'name': 'test-event',
            'start_date': now,
            'end_date': now,
            'attendance_target': 10,
            'sameday_reg': True,
            'track_each_day': False,
            'manager_id': self.webuser.user_id,
        }
        event = Event(**event_data)
        event.save(expected_attendees=[attendee.case_id])

        self.assertEqual(len(event.attendees), 1)
        self.assertTrue(isinstance(event.attendees[0], Attendee))

        attendee_case = CommCareCase.objects.get_case(event.attendees[0].case_id)
        self.assertEqual(attendee_case.type, Attendee.ATTENDEE_CASE_TYPE)

        subcases = attendee_case.get_subcases(f"event-{event.event_id}")
        self.assertEqual(len(subcases), 1)
        self.assertEqual(subcases[0].type, Attendee.EVENT_ATTENDEE_CASE_TYPE)

    def test_update_event_attendees(self):
        now = datetime.utcnow().date()
        attendee1 = self._create_attendee_on_domain('at1')
        attendee2 = self._create_attendee_on_domain('at2')

        event_data = {
            'domain': DOMAIN,
            'name': 'test-event',
            'start_date': now,
            'end_date': now,
            'attendance_target': 10,
            'sameday_reg': True,
            'track_each_day': False,
            'manager_id': self.webuser.user_id,
        }
        event = Event(**event_data)
        expected_attendees = [
            attendee1.case_id,
            attendee2.case_id,
        ]
        event.save(expected_attendees=expected_attendees)

        expected_case_ids = [a.case_id for a in event.attendees]

        self.assertTrue(attendee1.case_id in expected_case_ids)
        self.assertTrue(attendee2.case_id in expected_case_ids)

        attendee3 = self._create_attendee_on_domain('at3')

        event.save(
            expected_attendees=[
                attendee1.case_id,
                attendee3.case_id,
            ]
        )
        expected_case_ids = [a.case_id for a in event.attendees]

        self.assertTrue(attendee1.case_id in expected_case_ids)
        self.assertTrue(attendee2.case_id not in expected_case_ids)
        self.assertTrue(attendee3.case_id in expected_case_ids)

    def test_delete_event_removes_attendees_cases(self):
        now = datetime.utcnow().date()

        attendee = self._create_attendee_on_domain('attendee_to_remove')

        event_data = {
            'domain': DOMAIN,
            'name': 'test-event',
            'start_date': now,
            'end_date': now,
            'attendance_target': 10,
            'sameday_reg': True,
            'track_each_day': False,
            'manager_id': self.webuser.user_id,
        }
        event = Event(**event_data)
        event.save(expected_attendees=[attendee.case_id])

        extension_cases_ids = CommCareCaseIndex.objects.get_extension_case_ids(
            DOMAIN,
            [attendee.case_id]
        )
        self.assertEqual(len(extension_cases_ids), 1)

        event.delete()
        extension_cases_ids = CommCareCaseIndex.objects.get_extension_case_ids(
            DOMAIN,
            [attendee.case_id]
        )
        self.assertEqual(len(extension_cases_ids), 0)

    def _create_attendee_on_domain(self, username):
        user = create_mobile_worker(username, DOMAIN)
        attendee = Attendee(domain=DOMAIN)
        attendee.save(user_id=user.user_id)
        return attendee


def create_mobile_worker(username, domain):
    return CommCareUser.create(
        domain=domain,
        username=username,
        password="*****",
        created_by=None,
        created_via=None,
    )


def test_doctests():
    import corehq.apps.events.models as module
    results = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
