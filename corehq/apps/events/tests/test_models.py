from django.test import TestCase
from datetime import datetime

from corehq.apps.events.models import (
    Event,
    NOT_STARTED,
    Attendee,
)
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser, CommCareUser
from corehq.form_processor.models import CommCareCase
from corehq.apps.events.exceptions import InvalidAttendee
from corehq.apps.events.models import create_case_with_case_type


class TestAttendee(TestCase):

    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        for attendee in Attendee.objects.by_domain(cls.domain):
            attendee.delete()
        super().tearDownClass()

    def test_save_fails_without_user_id(self):
        try:
            Attendee(domain='bogus').save(user_id=None)
            self.assertTrue(False)
        except InvalidAttendee:
            self.assertTrue(True)

    def test_case_created_on_attendee_save(self):
        mobile_worker = create_mobile_worker('iworkmobiles', self.domain)
        domain_attendees = Attendee.objects.by_domain(self.domain)
        self.assertEqual(list(domain_attendees), [])

        attendee = Attendee(domain=self.domain)
        attendee.save(mobile_worker.user_id)

        domain_attendees = Attendee.objects.by_domain(self.domain)
        self.assertTrue(len(domain_attendees) == 1)
        self.assertTrue(domain_attendees[0].case_id is not None)

        attendee_case = CommCareCase.objects.get_case(domain_attendees[0].case_id, self.domain)
        self.assertEqual(attendee_case.name, mobile_worker.username)
        self.assertEqual(attendee_case.get_case_property('commcare_user_id'), mobile_worker.user_id)

    def test_case_deleted_on_attendee_delete(self):
        mobile_worker = create_mobile_worker('delete_me', self.domain)
        domain_attendees = Attendee.objects.by_domain(self.domain)
        self.assertEqual(list(domain_attendees), [])

        attendee = Attendee(domain=self.domain)
        attendee.save(mobile_worker.user_id)

        domain_attendees = Attendee.objects.by_domain(self.domain)
        case_id = domain_attendees[0].case_id
        attendee_case = CommCareCase.objects.get_case(case_id, self.domain)
        self.assertTrue(attendee_case is not None)
        self.assertTrue(attendee_case.deleted is False)

        attendee.delete()
        self.assertEqual(list(Attendee.objects.by_domain(self.domain)), [])
        attendee_case = CommCareCase.objects.get_case(case_id, self.domain)
        self.assertTrue(attendee_case.deleted is True)


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
        for attendee in Attendee.objects.by_domain(cls.domain):
            attendee.delete()
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

    def test_create_event_with_attendees(self):
        now = datetime.utcnow().date()

        attendee = self._create_attendee_on_domain('signmeup')

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

    def _create_attendee_on_domain(self, username):
        user = create_mobile_worker(username, self.domain)
        attendee = Attendee(domain=self.domain)
        attendee.save(user_id=user.user_id)
        return attendee


class TestModelUtils(TestCase):

    domain = 'test-domain'

    @classmethod
    def setUpClass(cls):
        super(TestModelUtils, cls).setUpClass()
        cls.created_cases = []

    @classmethod
    def tearDownClass(cls):
        for case_ in cls.created_cases:
            case_.delete()
        super(TestModelUtils, cls).tearDownClass()

    def test_create_case_with_case_type(self):
        case_ = create_case_with_case_type(
            case_type='muggle',
            case_args={
                'domain': self.domain,
                'properties': {'knows_the_function_of_a_rubber_duck': 'yes'}
            }
        )
        self.created_cases.append(case_)
        self.assertEqual(case_.type, 'muggle')
        self.assertEqual(case_.get_case_property('knows_the_function_of_a_rubber_duck'), 'yes')

    def test_create_case_with_case_type_with_index(self):
        parent_case = create_case_with_case_type(
            case_type='wizard',
            case_args={
                'domain': self.domain,
                'properties': {'knows_the_function_of_a_rubber_duck': 'no'},
            }
        )
        self.created_cases.append(parent_case)

        case_ = create_case_with_case_type(
            case_type='wizard',
            case_args={
                'domain': self.domain,
                'properties': {'plays_quidditch': 'yes'},
            },
            index={
                'parent_case_id': parent_case.case_id,
            }
        )
        self.created_cases.append(case_)

        extension_case = parent_case.get_subcases()[0]
        self.assertEqual(extension_case.type, 'wizard')
        self.assertEqual(extension_case.get_case_property('plays_quidditch'), 'yes')


def create_mobile_worker(username, domain):
    return CommCareUser.create(
        domain=domain,
        username=username,
        password="*****",
        created_by=None,
        created_via=None,
    )
