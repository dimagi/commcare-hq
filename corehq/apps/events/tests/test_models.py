import uuid

from django.test import TestCase
from datetime import datetime

from corehq.apps.events.models import (
    Event,
    Attendee,
)
from corehq.form_processor.tests.utils import create_case
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from corehq.form_processor.models import CommCareCase
from corehq.apps.es.tests.utils import es_test, ElasticTestMixin, populate_case_search_index


@es_test
class TestAttendee(ElasticTestMixin, TestCase):

    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.domain_attendee_cases = []

    @classmethod
    def tearDownClass(cls):
        CommCareCase.objects.hard_delete_cases(
            cls.domain,
            [case.case_id for case in cls.domain_attendee_cases]
        )
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_get_domain_cases(self):
        self._create_attendees_for_domain(2)
        cases = Attendee.get_domain_cases(self.domain)

        self.assertEqual(
            [c_.case_id for c_ in self.domain_attendee_cases].sort(),
            [c_.case_id for c_ in cases].sort()
        )

    def test_get_by_ids(self):
        self._create_attendees_for_domain(2)

        attendees_case_ids = [c_.case_id for c_ in self.domain_attendee_cases]
        attendees = Attendee.get_by_ids(attendees_case_ids, self.domain)

        self.assertTrue(len(attendees) == 2)
        self.assertTrue(isinstance(attendees[0], Attendee))
        self.assertTrue(attendees[0].domain == self.domain)
        self.assertTrue(isinstance(attendees[0].case, CommCareCase))

    def test_get_by_ids_empty(self):
        self.assertEqual(Attendee.get_by_ids([], self.domain), [])

    def test_get_by_event_id(self):
        event_id = 1

        self._create_attendees_for_domain(2)
        self._create_event_attendee([self.domain_attendee_cases[0]], event_id)

        event_attendees = Attendee.get_by_event_id(event_id, self.domain)

        self.assertEqual(len(event_attendees), 1)
        self.assertTrue(isinstance(event_attendees[0], Attendee))
        self.assertEqual(
            event_attendees[0].case.case_id,
            self.domain_attendee_cases[0].case_id
        )

    def test_get_by_event_id__only_ids(self):
        event_id = 1

        self._create_attendees_for_domain(2)
        self._create_event_attendee([self.domain_attendee_cases[0]], event_id)

        event_attendees = Attendee.get_by_event_id(event_id, self.domain, only_ids=True)

        self.assertEqual(len(event_attendees), 1)
        self.assertEqual(
            event_attendees[0],
            self.domain_attendee_cases[0].case_id
        )

    def _create_attendees_for_domain(self, count):
        for i in range(count):
            case_ = create_commcare_attendee_case(self.domain)
            self.domain_attendee_cases.append(case_)

        populate_case_search_index(self.domain_attendee_cases)

    def _create_event_attendee(self, attendees_cases, event_id):
        for attendee_case in attendees_cases:
            create_event_attendee_case(
                self.domain,
                event_id,
                attendee_case.case_id,
            )


class TestEvent(TestCase):

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
        event = Event._get_obj_from_data(event_data)

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
            case_type=Event.EVENT_CASE_TYPE,
            user_id=self.webuser.user_id,
            **case_args,
        )
        event = Event.get_obj_from_case(case_)

        self.assertTrue(isinstance(event, Event))
        self.assertTrue(event.case == case_)
        self.assertFalse(event.is_open)
        self.assertTrue(event.attendee_list_status == 'Accepted')
        self.assertEqual(event.expected_attendees, [])

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
        event = Event._get_obj_from_data(event_data)
        self.assertFalse(hasattr(event, 'case'))
        # A case will be created if the event does not have a case associated with it

        event.save()
        self.assertTrue(hasattr(event, 'case'))

        case_ = event.case
        self.assertTrue(isinstance(case_, CommCareCase))
        self.assertTrue(case_.case_id == event.event_id)
        self.assertTrue(case_.type == Event.EVENT_CASE_TYPE)
        self.assertEqual(event.expected_attendees, [])
        self.assertEqual(event.attendance_takers, [])

    def test_create_event_with_attendees(self):
        now = datetime.utcnow().date()
        attendee_case = create_commcare_attendee_case(self.domain)

        event_data = {
            'domain': self.domain,
            'name': 'test-event',
            'start_date': now,
            'end_date': now,
            'attendance_target': 10,
            'sameday_reg': True,
            'track_each_day': False,
            'manager': self.webuser,
            'expected_attendees': [attendee_case.case_id]
        }

        event = Event.create(event_data)

        self.assertEqual(len(event.expected_attendees), 1)
        self.assertTrue(isinstance(event.expected_attendees[0], Attendee))
        self.assertTrue(isinstance(event.expected_attendees[0].case, CommCareCase))
        self.assertEqual(event.expected_attendees[0].case.type, Attendee.ATTENDEE_CASE_TYPE)

        subcases = event.expected_attendees[0].case.get_subcases(f"event-{event.event_id}")
        self.assertEqual(len(subcases), 1)
        self.assertEqual(subcases[0].type, Attendee.EVENT_ATTENDEE_CASE_TYPE)

    def test_update_event_attendees(self):
        now = datetime.utcnow().date()
        attendee_case1 = create_commcare_attendee_case(self.domain)
        attendee_case2 = create_commcare_attendee_case(self.domain)

        event_data = {
            'domain': self.domain,
            'name': 'test-event',
            'start_date': now,
            'end_date': now,
            'attendance_target': 10,
            'sameday_reg': True,
            'track_each_day': False,
            'manager': self.webuser,
            'expected_attendees': [
                attendee_case1.case_id,
                attendee_case2.case_id,
            ]
        }

        event = Event.create(event_data)
        first_round_attendees = event.expected_attendees
        expected_case_ids = [c_.case.case_id for c_ in first_round_attendees]

        self.assertTrue(attendee_case1.case_id in expected_case_ids)
        self.assertTrue(attendee_case2.case_id in expected_case_ids)

        attendee_case3 = create_commcare_attendee_case(self.domain)

        event.save(
            attendees=[
                attendee_case1.case_id,
                attendee_case3.case_id,
            ]
        )
        second_round_attendees = event.expected_attendees
        expected_case_ids = [c_.case.case_id for c_ in second_round_attendees]

        self.assertTrue(attendee_case1.case_id in expected_case_ids)
        self.assertTrue(attendee_case2.case_id not in expected_case_ids)
        self.assertTrue(attendee_case3.case_id in expected_case_ids)


def create_commcare_attendee_case(domain):
    from corehq.apps.events.utils import create_case_with_case_type
    return create_case_with_case_type(
        case_type=Attendee.ATTENDEE_CASE_TYPE,
        case_args={
            'domain': domain,
            'properties': {
                'username': f'attendee_mctest@{uuid.uuid4().hex}'
            }
        },
    )


def create_event_attendee_case(domain, event_id, parent_case_id):
    from corehq.apps.events.utils import create_case_with_case_type, case_index_event_identifier
    return create_case_with_case_type(
        case_type=Attendee.EVENT_ATTENDEE_CASE_TYPE,
        case_args={
            'domain': domain,
            'properties': {
                'event_id': event_id
            }
        },
        index={
            'parent_case_id': parent_case_id,
            'identifier': case_index_event_identifier(event_id),
        }
    )
