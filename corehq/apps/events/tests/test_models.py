import doctest
from contextlib import contextmanager
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory, CaseStructure

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.util.test_utils import create_test_case

from ..models import (
    ATTENDEE_USER_ID_CASE_PROPERTY,
    DEFAULT_ATTENDEE_CASE_TYPE,
    EVENT_ATTENDEE_CASE_TYPE,
    NOT_STARTED,
    AttendanceTrackingConfig,
    AttendeeCase,
    Event,
    get_attendee_case_type,
    get_user_case_sharing_groups_for_events,
)

DOMAIN = 'test-domain'


class TestAttendeeCaseManager(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = CaseFactory(DOMAIN)

    @contextmanager
    def get_attendee_cases(self):
        case_type = get_attendee_case_type(DOMAIN)
        with create_test_case(
            DOMAIN,
            case_type,
            'Oliver Opencase',
        ) as open_case, create_test_case(
            DOMAIN,
            case_type,
            'Clarence Closedcase',
        ) as closed_case:
            self.factory.close_case(closed_case.case_id)
            yield open_case, closed_case

    def test_manager_returns_open_cases(self):
        with self.get_attendee_cases() as (open_case, closed_case):
            cases = AttendeeCase.objects.by_domain(DOMAIN)
            self.assertEqual(cases, [open_case])

    def test_manager_returns_closed_cases_as_well(self):
        with self.get_attendee_cases() as (open_case, closed_case):
            cases = AttendeeCase.objects.by_domain(DOMAIN, include_closed=True)
            self.assertEqual(cases, [open_case, closed_case])


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
        case_type = get_attendee_case_type(DOMAIN)
        with self._get_mobile_worker(username) as user:
            (attendee,) = self.factory.create_or_update_cases([CaseStructure(
                attrs={
                    'case_type': case_type,
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
        tomorrow = (datetime.utcnow() + timedelta(days=1)).date()
        event = Event(
            domain=DOMAIN,
            name='test-event',
            start_date=tomorrow,
            end_date=tomorrow,
            attendance_target=10,
            sameday_reg=True,
            track_each_day=False,
            manager_id=self.webuser.user_id,
        )
        event.save()

        self.assertEqual(event.status, NOT_STARTED)
        self.assertEqual(event.is_open, True)
        self.assertTrue(event.event_id is not None)

    def test_create_event_with_no_end_date(self):
        tomorrow = (datetime.utcnow() + timedelta(days=1)).date()
        event = Event(
            domain=DOMAIN,
            name='test-event',
            start_date=tomorrow,
            end_date=None,
            attendance_target=10,
            sameday_reg=True,
            track_each_day=False,
            manager_id=self.webuser.user_id,
        )
        event.save()

        self.assertEqual(event.status, NOT_STARTED)
        self.assertEqual(event.is_open, True)
        self.assertTrue(event.event_id is not None)
        self.assertTrue(event.end_date is None)

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

            attendee_case_type = get_attendee_case_type(DOMAIN)
            event_attendees = event.get_expected_attendees()

            self.assertEqual(len(event_attendees), 1)
            self.assertEqual(event_attendees[0].type, attendee_case_type)
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

    def test_create_event_with_attendance_taker(self):
        with self._get_mobile_worker('test-commcare-user') as commcare_user:
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
                attendance_taker_ids=[commcare_user.user_id]
            )
            event.save()

            self.assertEqual(event.get_total_attendance_takers(), 1)
            self.assertEqual(event.attendance_taker_ids[0], commcare_user.user_id)


class TestCaseSharingGroup(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.commcare_user = CommCareUser.create(
            domain=DOMAIN,
            username='test-attendance-taker',
            password='*****',
            created_by=None,
            created_via=None
        )

    @classmethod
    def tearDownClass(cls):
        cls.commcare_user.delete(None, None)
        cls.domain_obj.delete()
        super().tearDownClass()

    @contextmanager
    def _get_event(self, attendance_taker_list):
        today = datetime.utcnow().date()
        event = Event.objects.create(
            domain=DOMAIN,
            name='test-event-at',
            start_date=today,
            end_date=today,
            attendance_target=10,
            sameday_reg=True,
            track_each_day=False,
            manager_id='123',
            attendance_taker_ids=attendance_taker_list
        )
        try:
            yield event
        finally:
            event.delete()

    def test_get_user_case_sharing_groups_for_events(self):
        with self._get_event([self.commcare_user.user_id]) as event:
            groups = list(get_user_case_sharing_groups_for_events(self.commcare_user))
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]._id, event.group_id)
            self.assertEqual(groups[0].name, f"{event.name} Event")

    def test_no_user_case_sharing_groups_for_events(self):
        with self._get_event([]):
            groups = list(get_user_case_sharing_groups_for_events(self.commcare_user))
            self.assertEqual(len(groups), 0)


class GetAttendeeCaseTypeTest(TestCase):

    def test_config_does_not_exist(self):
        case_type = get_attendee_case_type('some-other-domain')
        self.assertEqual(case_type, DEFAULT_ATTENDEE_CASE_TYPE)

    def test_config(self):
        with self.example_config():
            case_type = get_attendee_case_type(DOMAIN)
            self.assertEqual(case_type, 'travailleur')

    @contextmanager
    def example_config(self):
        config = AttendanceTrackingConfig.objects.create(
            domain=DOMAIN,
            mobile_worker_attendees=False,
            attendee_case_type='travailleur',
        )
        try:
            yield
        finally:
            config.delete()


class EventCaseTests(TestCase):

    def setUp(self):
        today = datetime.utcnow().date()
        self.event = Event(
            name='Test Event',
            domain=DOMAIN,
            start_date=today,
            end_date=today,
            attendance_target=0,
        )
        self.event.save()

    def tearDown(self):
        try:
            self.event.delete()
        except AssertionError:
            pass  # self.event is already deleted

    def test_case(self):
        with self.assertRaises(CaseNotFound):
            CommCareCase.objects.get_case(self.event.case_id, DOMAIN)

        event_case = self.event.case  # Creates case
        case = CommCareCase.objects.get_case(self.event.case_id, DOMAIN)
        self.assertEqual(event_case, case)

    def test_delete_with_case(self):
        __ = self.event.case
        self.event.delete()
        case = CommCareCase.objects.get_case(self.event.case_id, DOMAIN)
        self.assertTrue(case.closed)

    def test_delete_without_case(self):
        self.event.delete()  # Does not raise error

    def test_default_uuids(self):
        today = datetime.utcnow().date()
        unsaved_event = Event(
            name='Test Event Too',
            domain=DOMAIN,
            start_date=today,
            end_date=today,
            attendance_target=0,
        )
        self.assertIsInstance(unsaved_event.event_id, UUID)
        self.assertIsInstance(unsaved_event._case_id, UUID)

    def test_uuid_hex_string(self):
        today = datetime.utcnow().date()
        case_id_hex_string = uuid4().hex
        unsaved_event = Event(
            name='Test Event 33.3',
            _case_id=case_id_hex_string,
            domain=DOMAIN,
            start_date=today,
            end_date=today,
            attendance_target=0,
        )
        self.assertIsInstance(unsaved_event._case_id, str)
        self.assertEqual(unsaved_event.case_id, case_id_hex_string)


def test_doctests():
    import corehq.apps.events.models as module
    results = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
