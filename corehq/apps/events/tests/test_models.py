import doctest
from contextlib import contextmanager
from datetime import datetime

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory, CaseStructure

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.util.test_utils import create_test_case

from ..models import (
    ATTENDEE_CASE_TYPE,
    ATTENDEE_USER_ID_CASE_PROPERTY,
    EVENT_ATTENDEE_CASE_TYPE,
    NOT_STARTED,
    AttendeeCase,
    Event,
)

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


class TestEventModel(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = CaseFactory(DOMAIN)
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
        super().tearDownClass()

    @contextmanager
    def _get_attendee(self, username):
        with self._get_mobile_worker(username) as user:
            (attendee,) = self.factory.create_or_update_cases([CaseStructure(
                attrs={
                    'case_type': ATTENDEE_CASE_TYPE,
                    'update': {
                        ATTENDEE_USER_ID_CASE_PROPERTY: user.user_id,
                    },
                    'create': True,
                }
            )])
            try:
                yield attendee
            finally:
                CommCareCase.objects.hard_delete_cases(
                    DOMAIN,
                    [attendee.case_id],
                )

    @contextmanager
    def _get_mobile_worker(self, username):
        mobile_worker = CommCareUser.create(
            domain=DOMAIN,
            username=username,
            password="*****",
            created_by=None,
            created_via=None,
        )
        try:
            yield mobile_worker
        finally:
            mobile_worker.delete(None, None)

    def test_create_event(self):
        today = datetime.utcnow().date()
        event = Event(
            domain=DOMAIN,
            name='test-event',
            start_date=today,
            end_date=today,
            attendance_target=10,
            sameday_reg=True,
            track_each_day=False,
            manager_id=self.webuser.user_id,
        )
        event.save()

        self.assertEqual(event.status, NOT_STARTED)
        self.assertEqual(event.is_open, True)
        self.assertTrue(event.event_id is not None)

    def test_create_event_with_attendees(self):
        with self._get_attendee('signmeup') as attendee:
            today = datetime.utcnow().date()
            event = Event(
                domain=DOMAIN,
                name='test-event',
                start_date=today,
                end_date=today,
                attendance_target=10,
                sameday_reg=True,
                track_each_day=False,
                manager_id=self.webuser.user_id,
            )
            event.save()
            event.set_expected_attendees([attendee])

            event_attendees = event.get_expected_attendees()

            self.assertEqual(len(event_attendees), 1)
            self.assertEqual(event_attendees[0].type, ATTENDEE_CASE_TYPE)
            self.assertEqual(event_attendees[0].case_id, attendee.case_id)

            attendee_subcases = event_attendees[0].get_subcases('attendee-host')
            self.assertEqual(len(attendee_subcases), 1)
            self.assertEqual(attendee_subcases[0].type, EVENT_ATTENDEE_CASE_TYPE)

            event_subcases = event.case.get_subcases('event-host')
            self.assertEqual(len(event_subcases), 1)
            self.assertEqual(event_subcases[0].type, EVENT_ATTENDEE_CASE_TYPE)
            self.assertEqual(event_subcases[0].case_id, attendee_subcases[0].case_id)

    def test_update_event_attendees(self):
        with self._get_attendee('at1') as attendee1, \
                self._get_attendee('at2') as attendee2, \
                self._get_attendee('at3') as attendee3:

            today = datetime.utcnow().date()
            event = Event(
                domain=DOMAIN,
                name='test-event',
                start_date=today,
                end_date=today,
                attendance_target=10,
                sameday_reg=True,
                track_each_day=False,
                manager_id=self.webuser.user_id,
            )
            event.save()

            event.set_expected_attendees([attendee1, attendee2])
            self.assertEqual(
                {a.case_id for a in event.get_expected_attendees()},
                {attendee1.case_id, attendee2.case_id}
            )

            event.set_expected_attendees([attendee1, attendee3])
            self.assertEqual(
                {a.case_id for a in event.get_expected_attendees()},
                {attendee1.case_id, attendee3.case_id}
            )

    def test_mark_attendance(self):
        def test_update_event_attendees(self):
            with self._get_attendee('att1') as attendee1, \
                    self._get_attendee('att2') as attendee2, \
                    self._get_attendee('att3') as attendee3:

                today = datetime.utcnow().date()
                event = Event(
                    domain=DOMAIN,
                    name='test-event',
                    start_date=today,
                    end_date=today,
                    attendance_target=10,
                    sameday_reg=True,
                    track_each_day=False,
                    manager_id=self.webuser.user_id,
                )
                event.save()
                event.set_expected_attendees([attendee1, attendee2, attendee3])
                event.mark_attendance([attendee1, attendee2], datetime.utcnow())
                self.assertEqual(
                    set(event.get_attended_attendees()),
                    {attendee1, attendee2}
                )

    def test_delete_event_removes_attendees_cases(self):
        with self._get_attendee('attendee_to_remove') as attendee:
            today = datetime.utcnow().date()
            event = Event(
                domain=DOMAIN,
                name='test-event',
                start_date=today,
                end_date=today,
                attendance_target=10,
                sameday_reg=True,
                track_each_day=False,
                manager_id=self.webuser.user_id,
            )
            event.save()
            event.set_expected_attendees([attendee])

            ext_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
                DOMAIN,
                [attendee.case_id],
                include_closed=False,
            )
            self.assertEqual(len(ext_case_ids), 1)

            event.delete()
            ext_case_ids = CommCareCaseIndex.objects.get_extension_case_ids(
                DOMAIN,
                [attendee.case_id],
                include_closed=False,
            )
            self.assertEqual(len(ext_case_ids), 0)


def test_doctests():
    import corehq.apps.events.models as module
    results = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
