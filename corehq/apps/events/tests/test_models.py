import doctest
from contextlib import contextmanager
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from django.test import TestCase

from casexml.apps.case.mock import CaseFactory, CaseStructure

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.hqcase.case_helper import CaseHelper
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.models import CommCareCase, CommCareCaseIndex
from corehq.util.test_utils import create_test_case
from corehq.form_processor.tests.utils import create_case

from ..exceptions import AttendeeTrackedException
from ..models import (
    ATTENDEE_USER_ID_CASE_PROPERTY,
    DEFAULT_ATTENDEE_CASE_TYPE,
    EVENT_ATTENDEE_CASE_TYPE,
    EVENT_NOT_STARTED,
    LOCATION_IDS_CASE_PROPERTY,
    PRIMARY_LOCATION_ID_CASE_PROPERTY,
    AttendanceTrackingConfig,
    AttendeeModel,
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
            cases = [m.case for m in AttendeeModel.objects.by_domain(DOMAIN)]
            self.assertEqual(cases, [open_case])

    def test_manager_returns_closed_cases_as_well(self):
        with self.get_attendee_cases() as (open_case, closed_case):
            cases = [m.case for m in AttendeeModel.objects.by_domain(
                DOMAIN,
                include_closed=True,
            )]
            self.assertEqual(cases, [open_case, closed_case])


@es_test(requires=[case_search_adapter], setup_class=True)
class TestByLocationId(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.country = LocationType.objects.create(
            domain=DOMAIN,
            name='Country',
        )
        cls.city = LocationType.objects.create(
            domain=DOMAIN,
            name='City',
            parent_type=cls.country,
        )
        cls.suriname = SQLLocation.objects.create(
            domain=DOMAIN,
            name='Suriname',
            location_id=str(uuid4()),
            location_type=cls.country,
        )
        cls.paramaribo = SQLLocation.objects.create(
            domain=DOMAIN,
            name='Paramaribo',
            location_id=str(uuid4()),
            location_type=cls.city,
            parent=cls.suriname,
        )

        case_type = get_attendee_case_type(DOMAIN)
        cls.country_attendee = create_case(
            DOMAIN,
            case_id=uuid4().hex,
            case_type=case_type,
            name='Countryboy',
            case_json={
                LOCATION_IDS_CASE_PROPERTY: cls.suriname.location_id,
            },
            save=True,
        )
        cls.city_attendee = create_case(
            DOMAIN,
            case_id=uuid4().hex,
            case_type=case_type,
            name='Citygirl',
            case_json={
                LOCATION_IDS_CASE_PROPERTY: cls.paramaribo.location_id,
            },
            save=True,
        )
        cls.both_attendee = create_case(
            DOMAIN,
            case_id=uuid4().hex,
            case_type=case_type,
            name='Everywhereguy',
            case_json={
                LOCATION_IDS_CASE_PROPERTY: ' '.join((
                    cls.suriname.location_id,
                    cls.paramaribo.location_id,
                ))
            },
            save=True,
        )
        case_search_adapter.bulk_index([
            cls.country_attendee,
            cls.city_attendee,
            cls.both_attendee,
        ], refresh=True)

    @classmethod
    def tearDownClass(cls):
        CommCareCase.objects.hard_delete_cases(DOMAIN, [
            cls.city_attendee.case_id,
            cls.country_attendee.case_id,
            cls.both_attendee.case_id,
        ])
        cls.paramaribo.delete()
        cls.suriname.delete()
        cls.city.delete()
        cls.country.delete()
        cls.domain_obj.delete()
        super().tearDownClass()

    def test_parent_location(self):
        models = AttendeeModel.objects.by_location_id(
            DOMAIN,
            self.suriname.location_id,
        )
        self.assertEqual(
            {m.case for m in models},
            {self.country_attendee, self.city_attendee, self.both_attendee},
        )

    def test_child_location(self):
        models = AttendeeModel.objects.by_location_id(
            DOMAIN,
            self.paramaribo.location_id,
        )
        self.assertEqual(
            {m.case for m in models},
            {self.city_attendee, self.both_attendee},
        )

    def test_location_id_empty(self):
        models = AttendeeModel.objects.by_location_id(DOMAIN, '')
        self.assertEqual([m.case for m in models], [])

    def test_location_id_none(self):
        models = AttendeeModel.objects.by_location_id(DOMAIN, None)
        self.assertEqual([m.case for m in models], [])


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

    @contextmanager
    def _get_location(self):
        location_type = LocationType.objects.create(
            domain=DOMAIN,
            name='Place',
        )
        location = SQLLocation.objects.create(
            domain=DOMAIN,
            name='Otherworld',
            location_id=str(uuid4()),
            location_type=location_type,
        )
        try:
            yield location
        finally:
            location.delete()
            location_type.delete()

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
        self.addCleanup(event.delete)

        self.assertEqual(event.status, EVENT_NOT_STARTED)
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
        self.addCleanup(event.delete)

        self.assertEqual(event.status, EVENT_NOT_STARTED)
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
            self.addCleanup(event.delete)
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
            self.addCleanup(event.delete)

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
            self.addCleanup(event.delete)
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
            self.addCleanup(event.delete)

            self.assertEqual(event.get_total_attendance_takers(), 1)
            self.assertEqual(event.attendance_taker_ids[0], commcare_user.user_id)

    def test_get_events_by_location(self):
        with self._get_location() as location:
            today = datetime.utcnow().date()
            event = Event.objects.create(
                domain=DOMAIN,
                name='test-event',
                start_date=today,
                end_date=today,
                location=location,
                attendance_target=0,
            )
            self.addCleanup(event.delete)

            events_by_loc = list(Event.objects.filter(location=location))
            self.assertEqual(events_by_loc, [event])

            location_events = list(location.event_set.all())
            self.assertEqual(location_events, [event])


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
        # Before save()
        case_type = get_attendee_case_type(DOMAIN)
        self.assertEqual(case_type, DEFAULT_ATTENDEE_CASE_TYPE)

        with self.example_config():
            case_type = get_attendee_case_type(DOMAIN)
            self.assertEqual(case_type, 'travailleur')

        # After delete()
        case_type = get_attendee_case_type(DOMAIN)
        self.assertEqual(case_type, DEFAULT_ATTENDEE_CASE_TYPE)

    @contextmanager
    def example_config(self):
        config = AttendanceTrackingConfig(
            domain=DOMAIN,
            mobile_worker_attendees=False,
            attendee_case_type='travailleur',
        )
        config.save()
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
        self.event.save()  # Creates case

    def test_delete_closes_case(self):
        case = CommCareCase.objects.get_case(self.event.case_id, DOMAIN)
        self.assertFalse(case.closed)

        self.event.delete()
        case = CommCareCase.objects.get_case(self.event.case_id, DOMAIN)
        self.assertTrue(case.closed)

    def test_default_uuids(self):
        today = datetime.utcnow().date()
        event = Event(
            name='Test Event Too',
            domain=DOMAIN,
            start_date=today,
            end_date=today,
            attendance_target=0,
        )
        self.assertIsInstance(event.event_id, UUID)
        self.assertIsNone(event._case_id)

    def test_save_creates_case(self):
        today = datetime.utcnow().date()
        event = Event(
            name='Test Event Too',
            domain=DOMAIN,
            start_date=today,
            end_date=today,
            attendance_target=0,
        )
        self.assertIsNone(event._case_id)

        event.save()
        self.assertIsInstance(event._case_id, UUID)

        event.delete()

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


class TestAttendeeModel(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.webuser = WebUser.create(
            DOMAIN,
            'test-user',
            'mockmock',
            None,
            None
        )

    @classmethod
    def tearDownClass(cls):
        cls.webuser.delete(None, None)
        cls.domain_obj.delete()
        super().tearDownClass()

    @staticmethod
    @contextmanager
    def get_case(with_properties=True):
        helper = CaseHelper(domain=DOMAIN)
        if with_properties:
            properties = {
                LOCATION_IDS_CASE_PROPERTY: 'abc123 def456',
                PRIMARY_LOCATION_ID_CASE_PROPERTY: 'abc123',
                ATTENDEE_USER_ID_CASE_PROPERTY: 'c0ffee',
            }
        else:
            properties = {}
        helper.create_case({
            'case_name': 'Cho Chang',
            'case_type': get_attendee_case_type(DOMAIN),
            'properties': properties,
        })
        try:
            yield helper.case
        finally:
            helper.close()

    def test_model_init(self):
        with self.get_case() as case:
            model = AttendeeModel(case=case, domain=DOMAIN)
            self.assertEqual(str(model.case_id), case.case_id)
            self.assertEqual(model.name, case.name)
            self.assertEqual(model.domain, case.domain)
            loc_ids_str = case.get_case_property(LOCATION_IDS_CASE_PROPERTY)
            self.assertEqual(model.locations, loc_ids_str.split())
            self.assertEqual(
                model.primary_location,
                case.get_case_property(PRIMARY_LOCATION_ID_CASE_PROPERTY)
            )
            self.assertEqual(
                model.user_id,
                case.get_case_property(ATTENDEE_USER_ID_CASE_PROPERTY)
            )

    def test_model_init_defaults(self):
        with self.get_case(with_properties=False) as case:
            model = AttendeeModel(case=case, domain=DOMAIN)
            self.assertEqual(str(model.case_id), case.case_id)
            self.assertEqual(model.name, case.name)
            self.assertEqual(model.domain, case.domain)
            self.assertEqual(model.locations, [])
            self.assertIsNone(model.primary_location)
            self.assertIsNone(model.user_id)

    def test_model_save(self):
        with self.get_case() as case:
            model = AttendeeModel(case=case, domain=DOMAIN)
            model.locations = ['def456']
            model.primary_location = 'def456'
            model.user_id = 'deadbeef'
            model.save()

            reloaded = CommCareCase.objects.get_case(case.case_id, DOMAIN)
            self.assertEqual(
                reloaded.get_case_property(LOCATION_IDS_CASE_PROPERTY),
                'def456'
            )
            self.assertEqual(
                reloaded.get_case_property(PRIMARY_LOCATION_ID_CASE_PROPERTY),
                'def456'
            )
            self.assertEqual(
                reloaded.get_case_property(ATTENDEE_USER_ID_CASE_PROPERTY),
                'deadbeef'
            )

    def test_model_save_defaults(self):
        with self.get_case(with_properties=False) as case:
            model = AttendeeModel(case=case, domain=DOMAIN)
            model.save()

            reloaded = CommCareCase.objects.get_case(case.case_id, DOMAIN)
            self.assertEqual(
                reloaded.get_case_property(LOCATION_IDS_CASE_PROPERTY),
                ''
            )
            self.assertEqual(
                reloaded.get_case_property(PRIMARY_LOCATION_ID_CASE_PROPERTY),
                ''
            )
            self.assertEqual(
                reloaded.get_case_property(ATTENDEE_USER_ID_CASE_PROPERTY),
                ''
            )

    def test_model_save_form_values(self):
        with self.get_case() as case:
            model = AttendeeModel(case=case, domain=DOMAIN)
            model.locations = "['abc123', 'def456']"
            model.primary_location = 'def456'
            model.save()

            reloaded = CommCareCase.objects.get_case(case.case_id, DOMAIN)
            self.assertEqual(
                reloaded.get_case_property(LOCATION_IDS_CASE_PROPERTY),
                'abc123 def456'
            )
            self.assertEqual(
                reloaded.get_case_property(PRIMARY_LOCATION_ID_CASE_PROPERTY),
                'def456'
            )
            self.assertEqual(
                reloaded.get_case_property(ATTENDEE_USER_ID_CASE_PROPERTY),
                'c0ffee'
            )

    def test_model_delete(self):
        with self.get_case(with_properties=False) as case:
            model = AttendeeModel(case=case, domain=DOMAIN)
            model.save()
            reloaded = CommCareCase.objects.get_case(case.case_id, DOMAIN)
            self.assertFalse(reloaded.get_case_property('closed'))
            model.delete()
            reloaded = CommCareCase.objects.get_case(case.case_id, DOMAIN)
            self.assertTrue(reloaded.get_case_property('closed'))

    def test_has_attended_events(self):
        today = datetime.utcnow().date()
        event = Event(
            domain=DOMAIN,
            name='test-event',
            start_date=today,
            end_date=today,
            attendance_target=10,
            sameday_reg=True,
            track_each_day=False,
            manager_id=self.webuser.user_id
        )
        event.save()
        with self.get_case(with_properties=False) as case:
            attendee = AttendeeModel(case=case, domain=DOMAIN)
            attendee.save()

            self.assertFalse(attendee.has_attended_events())
            event.mark_attendance([case], datetime.now())

        self.assertTrue(attendee.has_attended_events())
        self.assertRaises(
            AttendeeTrackedException,
            attendee.delete
        )


def test_doctests():
    import corehq.apps.events.models as module
    results = doctest.testmod(module, optionflags=doctest.ELLIPSIS)
    assert results.failed == 0
